package buzz.kirbytrim.mobile

import java.text.Normalizer
import java.util.Locale
import org.json.JSONArray
import org.json.JSONObject

/** Un jeu du catalogue du site. */
data class Game(
    val system: String,
    val file: String,
    val title: String,
    val region: String?,
    val year: String?,
    val size: Long,
    val cover: String?,
)

/** Une console et les jeux qu'elle contient. */
data class Console(
    val id: String,
    val label: String,
    val games: List<Game>,
)

/** Catalogue complet renvoyé par « /api/library ». */
data class Library(
    val totalGames: Int,
    val consoles: List<Console>,
)

/**
 * Cores Android conseillés pour chaque console, du plus souhaitable au moins.
 * Les noms sont ceux des fichiers sans « _libretro_android.so » ; on ne garde
 * que les cores réellement installés (voir Emulators.installedCoresFor).
 */
private val ANDROID_CORES: Map<String, List<String>> = mapOf(
    "nes" to listOf("fceumm", "mesen", "nestopia", "quicknes"),
    "snes" to listOf("snes9x", "snes9x2010", "bsnes", "mesen-s"),
    "gb" to listOf("gambatte", "sameboy", "gearboy"),
    "gba" to listOf("mgba", "gpsp", "vba_next"),
    "n64" to listOf("mupen64plus_next", "parallel_n64"),
    "nds" to listOf("melondsds", "melonds", "desmume", "desmume2015"),
    "psx" to listOf("pcsx_rearmed", "swanstation", "mednafen_psx_hw", "mednafen_psx"),
    "segaMD" to listOf("genesis_plus_gx", "picodrive"),
    "segaMS" to listOf("genesis_plus_gx", "smsplus", "picodrive"),
    "segaGG" to listOf("genesis_plus_gx", "picodrive"),
    "sega32x" to listOf("picodrive"),
    "segaSaturn" to listOf("mednafen_saturn", "kronos", "yabause", "yabasanshiro"),
    "dreamcast" to listOf("flycast"),
    "gamecube" to listOf("dolphin"),
    "wii" to listOf("dolphin"),
    "ps2" to listOf("pcsx2"),
    "3ds" to listOf("azahar", "citra", "citra2018"),
    "arcade" to listOf("fbneo", "mame2003_plus", "mame2003"),
    "pce" to listOf("mednafen_pce", "mednafen_pce_fast", "mednafen_supergrafx"),
    "atari2600" to listOf("stella2014", "stella"),
    "lynx" to listOf("handy", "mednafen_lynx"),
    "c64" to listOf("vice_x64sc", "vice_x64"),
    "vb" to listOf("mednafen_vb", "beetle_vb"),
    "cpc" to listOf("cap32", "crocods"),
    "apple2" to listOf("applewin"),
    "pc88" to listOf("quasi88"),
    "pokemini" to listOf("pokemini"),
)

/** Cores conseillés pour cette console (peut être vide). */
fun androidCores(system: String): List<String> = ANDROID_CORES[system].orEmpty()

/** Lit le catalogue du site et transforme les jaquettes en adresses complètes. */
fun parseLibrary(json: String, siteUrl: String): Library {
    val base = siteUrl.trimEnd('/')
    val root = JSONObject(json)
    val systems = root.optJSONArray("systems") ?: JSONArray()
    val consoles = ArrayList<Console>(systems.length())

    for (index in 0 until systems.length()) {
        val system = systems.getJSONObject(index)
        val id = system.optString("id")
        if (id.isEmpty()) continue
        val gamesJson = system.optJSONArray("games") ?: JSONArray()
        val games = ArrayList<Game>(gamesJson.length())
        for (gameIndex in 0 until gamesJson.length()) {
            val game = gamesJson.getJSONObject(gameIndex)
            val file = game.optString("file")
            if (file.isEmpty()) continue
            val rawCover = game.optString("cover", "")
            val cover = when {
                rawCover.isBlank() -> null
                rawCover.startsWith("/") -> base + rawCover
                else -> rawCover
            }
            games.add(
                Game(
                    system = game.optString("system", id),
                    file = file,
                    title = game.optString("title", file),
                    region = game.optString("region", "").ifBlank { null },
                    year = game.optString("year", "").ifBlank { null },
                    size = game.optLong("size", 0L),
                    cover = cover,
                )
            )
        }
        if (games.isEmpty()) continue
        consoles.add(Console(id, system.optString("label", id), games))
    }

    return Library(root.optInt("totalGames", consoles.sumOf { it.games.size }), consoles)
}

private val COMBINING_MARKS = Regex("\\p{Mn}+")

/** Minuscules sans accents, pour la recherche. */
fun normalizeText(value: String): String =
    Normalizer.normalize(value.lowercase(Locale.ROOT), Normalizer.Form.NFD)
        .replace(COMBINING_MARKS, "")

/** « 2.4 Mo », « 512 Ko »… */
fun formatSize(bytes: Long): String {
    if (bytes <= 0) return "taille inconnue"
    val units = listOf("o", "Ko", "Mo", "Go")
    var size = bytes.toDouble()
    var unit = 0
    while (size >= 1024 && unit < units.size - 1) {
        size /= 1024
        unit += 1
    }
    return if (unit == 0) "$bytes o" else String.format(Locale.FRANCE, "%.1f %s", size, units[unit])
}
