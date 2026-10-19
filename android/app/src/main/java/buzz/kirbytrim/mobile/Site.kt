package buzz.kirbytrim.mobile

import java.io.BufferedInputStream
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/** Accès HTTP au site : catalogue et ROMs. */
object Site {

    /** Lit une adresse et renvoie le texte (catalogue JSON par ex.). */
    fun fetchText(url: String, timeoutMs: Int = 20000): String {
        val connection = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = timeoutMs
            readTimeout = timeoutMs
            requestMethod = "GET"
            setRequestProperty("User-Agent", USER_AGENT)
            setRequestProperty("Accept", "application/json")
        }
        try {
            val code = connection.responseCode
            if (code !in 200..299) throw IllegalStateException("HTTP $code")
            return connection.inputStream.bufferedReader().use { it.readText() }
        } finally {
            connection.disconnect()
        }
    }

    /** Adresse d'une ROM sur le site. */
    fun romUrl(siteUrl: String, system: String, file: String): String =
        "${siteUrl.trimEnd('/')}/roms/${encode(system)}/${encode(file)}"

    private fun encode(value: String): String =
        URLEncoder.encode(value, "UTF-8").replace("+", "%20")

    const val USER_AGENT = "KirbyRetroMobile/0.2"
}

/**
 * Téléchargement d'une ROM, avec progression et annulation.
 * Le fichier est écrit en « .part » puis renommé : pas de ROM tronquée.
 */
class RomDownload(
    private val url: String,
    private val destination: File,
    private val listener: Listener,
) {

    interface Listener {
        fun onProgress(read: Long, total: Long)
        fun onFinished(file: File)
        fun onFailed(error: Exception)
    }

    @Volatile
    private var cancelled = false
    private var connection: HttpURLConnection? = null
    private var thread: Thread? = null

    fun start() {
        if (thread != null) return
        val worker = Thread { run() }
        worker.isDaemon = true
        thread = worker
        worker.start()
    }

    fun cancel() {
        cancelled = true
        connection?.disconnect()
    }

    private fun run() {
        val part = File(destination.parentFile, destination.name + ".part")
        try {
            destination.parentFile?.mkdirs()
            val http = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = 20000
                readTimeout = 30000
                setRequestProperty("User-Agent", Site.USER_AGENT)
            }
            connection = http
            val code = http.responseCode
            if (code !in 200..299) throw IllegalStateException("HTTP $code")
            val total = http.contentLengthLong.takeIf { it > 0 } ?: 0L
            var read = 0L
            http.inputStream.use { raw ->
                BufferedInputStream(raw, BUFFER_SIZE).use { source ->
                    FileOutputStream(part).use { output ->
                        val buffer = ByteArray(BUFFER_SIZE)
                        while (true) {
                            if (cancelled) throw InterruptedException("téléchargement annulé")
                            val count = source.read(buffer)
                            if (count < 0) break
                            output.write(buffer, 0, count)
                            read += count
                            listener.onProgress(read, total)
                        }
                        output.flush()
                    }
                }
            }
            if (cancelled) throw InterruptedException("téléchargement annulé")
            if (destination.exists()) destination.delete()
            if (!part.renameTo(destination)) throw IllegalStateException("écriture impossible")
            listener.onFinished(destination)
        } catch (error: Exception) {
            part.delete()
            listener.onFailed(error)
        } finally {
            connection?.disconnect()
        }
    }

    companion object {
        private const val BUFFER_SIZE = 1 shl 16
    }
}
