package com.crosslink.app

import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.Socket
import java.net.SocketTimeoutException
import java.util.concurrent.Executors

/** UDP 搜索同网段的电脑：广播一句探测，收电脑回的 JSON。 */
object Discovery {

    data class Found(val name: String, val host: String, val port: Int, val needPin: Boolean)

    /** 电脑端口被占用时会自动往后挪，所以这里探一段端口，而不是只探 8788。 */
    private val PORTS = (8788..8799).toList()

    fun search(port: Int = 8788, timeoutMs: Int = 2500): List<Found> {
        val out = LinkedHashMap<String, Found>()
        DatagramSocket().use { sock ->
            sock.broadcast = true
            sock.soTimeout = 300
            val probe = "CROSSLINK?".toByteArray()

            val targets = LinkedHashSet<InetAddress>()
            runCatching { targets.add(InetAddress.getByName("255.255.255.255")) }
            runCatching {
                NetworkInterface.getNetworkInterfaces().toList().forEach { nif ->
                    runCatching {
                        nif.interfaceAddresses.forEach { ia ->
                            ia.broadcast?.let { targets.add(it) }
                        }
                    }
                }
            }
            targets.forEach { addr ->
                PORTS.forEach { p ->
                    runCatching {
                        sock.send(DatagramPacket(probe, probe.size, addr, p))
                    }
                }
            }

            val deadline = System.currentTimeMillis() + timeoutMs
            val buf = ByteArray(2048)
            while (System.currentTimeMillis() < deadline) {
                val pkt = DatagramPacket(buf, buf.size)
                try {
                    sock.receive(pkt)
                } catch (_: SocketTimeoutException) {
                    continue
                } catch (_: Exception) {
                    break
                }
                val json = runCatching {
                    JSONObject(String(pkt.data, 0, pkt.length, Charsets.UTF_8))
                }.getOrNull() ?: continue
                if (json.optString("t") != "crosslink") continue
                val host = pkt.address?.hostAddress ?: continue
                out[host] = Found(
                    json.optString("name", "电脑"),
                    host,
                    json.optInt("port", port),
                    json.optBoolean("pin"),
                )
            }
        }
        return out.values.toList()
    }

    /**
     * 兜底发现：不靠广播，直接扫自己所在的 /24 网段，谁开了 CrossLink 就问一句
     * 它的 /api/state（HTTP+Tcp，路由器拦广播时也能用）。
     * 对应 LocalSend 的 "Scans one particular subnet with traditional HTTP/TCP discovery"。
     */
    fun scanSubnet(port: Int = 8788, connectTimeoutMs: Int = 260): List<Found> {
        val local = localIpv4() ?: return emptyList()
        val prefix = local.substringBeforeLast('.', "")
        if (prefix.isEmpty()) return emptyList()
        val pool = Executors.newFixedThreadPool(32)
        return try {
            val tasks = (1..254).flatMap { i ->
                val host = "$prefix.$i"
                // 每台主机只试几个最可能的端口，避免 254×12 次连接太慢
                listOf(8788, 8789, 8790, 8795).map { p ->
                pool.submit<Found?> {
                    try {
                        Socket().use { sock ->
                            sock.connect(InetSocketAddress(host, p), connectTimeoutMs)
                            sock.soTimeout = 800
                            val req = ("GET /api/state HTTP/1.0\r\nHost: $host\r\n" +
                                "User-Agent: CrossLink\r\nConnection: close\r\n\r\n")
                            sock.getOutputStream().write(req.toByteArray())
                            sock.getOutputStream().flush()
                            val body = sock.getInputStream().readBytes().toString(Charsets.UTF_8)
                            val json = JSONObject(body.substringAfter("\r\n\r\n", ""))
                            val app = json.optJSONObject("app") ?: return@submit null
                            Found(
                                app.optString("name", "电脑"),
                                host,
                                app.optInt("port", p),
                                json.optBoolean("require_pin"),
                            )
                        }
                    } catch (_: Exception) {
                        null
                    }
                }
                }
            }
            tasks.mapNotNull { it.get() }
        } finally {
            pool.shutdownNow()
        }
    }

    /** 本机的一个 IPv4（优先 192.168 / 10. 这类家用网段）。 */
    fun localIpv4(): String? {
        val all = mutableListOf<String>()
        runCatching {
            NetworkInterface.getNetworkInterfaces().toList().forEach { nif ->
                if (!nif.isUp) return@forEach
                nif.interfaceAddresses.forEach { ia ->
                    val ip = ia.address?.hostAddress ?: return@forEach
                    if (ip.contains(':')) return@forEach      // 跳过 IPv6
                    if (ip.startsWith("127.") || ip.startsWith("169.254.")) return@forEach
                    all.add(ip)
                }
            }
        }
        return all.firstOrNull { it.startsWith("192.168.") }
            ?: all.firstOrNull { it.startsWith("10.") }
            ?: all.firstOrNull()
    }
}
