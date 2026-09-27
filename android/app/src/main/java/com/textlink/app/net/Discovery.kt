package com.textlink.app.net

import android.content.Context
import android.net.wifi.WifiManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.SocketTimeoutException
import java.util.Collections
import java.util.concurrent.ConcurrentHashMap

/**
 * 局域网自动发现。电脑端（TextLink-PC.exe）在 UDP 8766 上应答探测包。
 *
 * 分两级策略，尽量在"路由器屏蔽广播"的环境下也能找到电脑：
 *   1) 广播探测：向 255.255.255.255 和各网卡的定向广播地址发包（最快）；
 *   2) 单播扫描：如果 3 秒还没找到任何电脑，就把本网段 1~254 逐个发一遍
 *      （有些路由器/手机不允许广播，但单播一定通）。
 */
class Discovery(
    private val appContext: Context?,
    private val scope: CoroutineScope
) {

    private val _devices = MutableStateFlow<List<PcDevice>>(emptyList())
    val devices: StateFlow<List<PcDevice>> = _devices

    private var job: Job? = null
    @Volatile private var socket: DatagramSocket? = null
    private val found = ConcurrentHashMap<String, PcDevice>()
    private var multicastLock: WifiManager.MulticastLock? = null

    fun start() {
        if (job?.isActive == true) return
        acquireMulticastLock()
        job = scope.launch { run() }
    }

    fun stop() {
        job?.cancel()
        job = null
        closeSocket()
        releaseMulticastLock()
    }

    fun clear() {
        found.clear()
        _devices.value = emptyList()
    }

    // -- 内部实现 --------------------------------------------------------
    private fun acquireMulticastLock() {
        val context = appContext ?: return
        try {
            val wifi = context.applicationContext
                .getSystemService(Context.WIFI_SERVICE) as WifiManager
            val lock = wifi.createMulticastLock("textlink-discovery")
            lock.setReferenceCounted(false)
            lock.acquire()
            multicastLock = lock
        } catch (_: Exception) {
            // 拿不到锁也能用：广播可能被驱动过滤，还有单播扫描兜底
        }
    }

    private fun releaseMulticastLock() {
        try {
            multicastLock?.release()
        } catch (_: Exception) {
        }
        multicastLock = null
    }

    private fun closeSocket() {
        try {
            socket?.close()
        } catch (_: Exception) {
        }
        socket = null
    }

    private suspend fun run() = withContext(Dispatchers.IO) {
        val sock = openSocket() ?: return@withContext
        socket = sock
        var lastBroadcast = 0L
        var lastSweep = 0L
        val startedAt = System.currentTimeMillis()

        while (isActive) {
            val now = System.currentTimeMillis()

            // 1) 广播探测
            if (now - lastBroadcast > 1200) {
                lastBroadcast = now
                sendProbe(sock, broadcastAddresses())
            }

            // 2) 兜底：单播扫描本网段
            val nothingFound = found.isEmpty()
            val sweepInterval = if (nothingFound) 5000L else 20000L
            val waitedLongEnough = now - startedAt > 2500
            if (waitedLongEnough && now - lastSweep > sweepInterval) {
                lastSweep = now
                sendProbe(sock, subnetTargets())
            }

            try {
                val buffer = ByteArray(4096)
                val packet = DatagramPacket(buffer, buffer.size)
                sock.receive(packet)
                handlePacket(packet)
            } catch (_: SocketTimeoutException) {
                // 正常，继续
            } catch (e: Exception) {
                if (!isActive) break
            }

            pruneAndPublish()
        }
        closeSocket()
    }

    private fun openSocket(): DatagramSocket? {
        // 优先绑固定端口：这样电脑端主动广播的 beacon 也能收到
        try {
            return DatagramSocket(null).apply {
                reuseAddress = true
                broadcast = true
                bind(InetSocketAddress(Protocol.UDP_PORT))
                soTimeout = 900
            }
        } catch (_: Exception) {
        }
        return try {
            DatagramSocket().apply {
                reuseAddress = true
                broadcast = true
                soTimeout = 900
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun sendProbe(sock: DatagramSocket, targets: List<InetAddress>) {
        val data = Protocol.probe()
        for (address in targets) {
            try {
                sock.send(DatagramPacket(data, data.size, address, Protocol.UDP_PORT))
            } catch (_: Exception) {
            }
        }
    }

    private fun handlePacket(packet: DatagramPacket) {
        val text = String(packet.data, 0, packet.length)
        val obj = try {
            JSONObject(text)
        } catch (_: Exception) {
            return
        }
        if (obj.optString("app") != Protocol.APP_ID) return
        if (obj.optString("t") != "beacon") return
        val host = packet.address?.hostAddress ?: return
        val device = PcDevice(
            name = obj.optString("name", "Windows 电脑"),
            host = host,
            port = obj.optInt("port", Protocol.DEFAULT_PORT),
            needsPin = obj.optBoolean("needPin", true)
        )
        found[device.key] = device
    }

    private fun pruneAndPublish() {
        val cutoff = System.currentTimeMillis() - 9000
        val iterator = found.entries.iterator()
        while (iterator.hasNext()) {
            if (iterator.next().value.lastSeen < cutoff) iterator.remove()
        }
        _devices.value = found.values.sortedBy { it.name }
    }

    /** 广播地址：255.255.255.255 + 每张网卡的定向广播。 */
    private fun broadcastAddresses(): List<InetAddress> {
        val result = mutableListOf<InetAddress>()
        try {
            result.add(InetAddress.getByName("255.255.255.255"))
        } catch (_: Exception) {
        }
        forEachLocalIPv4 { _interfaceAddress ->
            val broadcast = _interfaceAddress.broadcast ?: return@forEachLocalIPv4
            if (!result.contains(broadcast)) result.add(broadcast)
        }
        return result
    }

    /** 本网段所有可能的主机地址（默认扫 /24，最多 254 个）。 */
    private fun subnetTargets(): List<InetAddress> {
        val result = mutableListOf<InetAddress>()
        val seen = HashSet<String>()
        forEachLocalIPv4 { interfaceAddress ->
            val address = interfaceAddress.address
            val bytes = address.address
            if (bytes.size != 4) return@forEachLocalIPv4
            val prefix = "${bytes[0].toInt() and 0xFF}.${bytes[1].toInt() and 0xFF}." +
                "${bytes[2].toInt() and 0xFF}"
            for (host in 1..254) {
                val ip = "$prefix.$host"
                if (!seen.add(ip)) continue
                try {
                    result.add(InetAddress.getByName(ip))
                } catch (_: Exception) {
                }
            }
        }
        return result
    }

    private fun forEachLocalIPv4(action: (java.net.InterfaceAddress) -> Unit) {
        try {
            for (nif in Collections.list(NetworkInterface.getNetworkInterfaces())) {
                if (!nif.isUp || nif.isLoopback) continue
                for (interfaceAddress in nif.interfaceAddresses) {
                    val address = interfaceAddress.address
                    if (address !is Inet4Address) continue
                    val first = address.address[0].toInt() and 0xFF
                    if (first == 169 || first == 127) continue   // 自动私有地址/回环，跳过
                    action(interfaceAddress)
                }
            }
        } catch (_: Exception) {
        }
    }
}
