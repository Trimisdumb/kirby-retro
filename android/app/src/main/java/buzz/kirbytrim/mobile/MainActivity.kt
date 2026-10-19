package buzz.kirbytrim.mobile

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.Editable
import android.text.TextWatcher
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.appbar.MaterialToolbar
import com.google.android.material.chip.Chip
import com.google.android.material.chip.ChipGroup
import java.io.File

/**
 * Bibliothèque du site en appli native : recherche, consoles, téléchargement
 * des ROMs puis lancement dans RetroArch — la même idée que le launcher PC.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var prefs: Prefs
    private lateinit var roms: RomStore
    private lateinit var adapter: GameAdapter
    private lateinit var toolbar: MaterialToolbar
    private lateinit var statusLine: TextView
    private lateinit var chips: ChipGroup

    private val emulator = EmulatorState()
    private val handler = Handler(Looper.getMainLooper())
    private val resetStatus = Runnable { updateStatus() }

    private var library: Library? = null
    private var consoles: List<Console> = emptyList()
    private var filter = "all"
    private var query = ""
    private var lastError: String? = null
    private var receiverRegistered = false
    private var coreAttempts = 0
    private var hadAccess = false

    /** RetroArch répond avec la liste de ses cores installés. */
    private val coresReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            if (intent.action != Emulators.ACTION_CORES_RESULT) return
            emulator.cores = intent.getStringArrayExtra(Emulators.EXTRA_CORES)?.toList().orEmpty()
            emulator.coresKnown = true
            updateStatus()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        prefs = Prefs(this)
        roms = RomStore(prefs)

        toolbar = findViewById(R.id.toolbar)
        statusLine = findViewById(R.id.status)
        chips = findViewById(R.id.chips)
        val search = findViewById<EditText>(R.id.search)
        val grid = findViewById<RecyclerView>(R.id.grid)

        adapter = GameAdapter { console, game -> openGame(console, game) }
        adapter.isDownloaded = { game -> roms.exists(game.system, game.file) }
        grid.layoutManager = GridLayoutManager(this, columns())
        grid.adapter = adapter

        toolbar.inflateMenu(R.menu.menu_main)
        toolbar.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                R.id.action_refresh -> {
                    loadLibrary(force = true)
                    true
                }

                R.id.action_settings -> {
                    openSettings()
                    true
                }

                else -> false
            }
        }

        search.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(text: CharSequence?, start: Int, count: Int, after: Int) = Unit

            override fun onTextChanged(text: CharSequence?, start: Int, before: Int, count: Int) = Unit

            override fun afterTextChanged(text: Editable?) {
                query = text?.toString().orEmpty()
                applyFilters()
            }
        })

        hadAccess = StorageAccess.hasAccess(this)
        loadCache()
        loadLibrary(force = false)
        findEmulator()
        updateStatus()
    }

    override fun onResume() {
        super.onResume()
        val access = StorageAccess.hasAccess(this)
        if (access && !hadAccess) status("Accès aux fichiers accordé ✓")
        hadAccess = access
        adapter.notifyDataSetChanged()
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        if (receiverRegistered) {
            try {
                unregisterReceiver(coresReceiver)
            } catch (error: IllegalArgumentException) {
                // déjà décroché
            }
        }
        super.onDestroy()
    }

    private fun columns(): Int = (resources.configuration.screenWidthDp / 110).coerceIn(2, 6)

    // --------------------------------------------------------- bibliothèque

    private fun loadCache() {
        val file = File(cacheDir, CACHE_FILE)
        if (!file.isFile || prefs.cacheSite != prefs.siteUrl) return
        try {
            applyLibrary(parseLibrary(file.readText(), prefs.siteUrl))
        } catch (error: Exception) {
            file.delete()
        }
    }

    private fun loadLibrary(force: Boolean) {
        if (force) lastError = null
        toolbar.subtitle = getString(R.string.library_loading)
        val site = prefs.siteUrl
        val worker = Thread {
            try {
                val text = Site.fetchText(site + "/api/library")
                val parsed = parseLibrary(text, site)
                runOnUiThread {
                    File(cacheDir, CACHE_FILE).writeText(text)
                    prefs.cacheSite = site
                    lastError = null
                    applyLibrary(parsed)
                    status("${parsed.totalGames} jeux · ${parsed.consoles.size} consoles")
                }
            } catch (error: Exception) {
                runOnUiThread {
                    lastError = error.message ?: error.javaClass.simpleName
                    if (library == null) toolbar.subtitle = "hors ligne"
                    updateStatus()
                }
            }
        }
        worker.isDaemon = true
        worker.start()
    }

    private fun applyLibrary(parsed: Library) {
        library = parsed
        consoles = parsed.consoles
        toolbar.subtitle = "${parsed.totalGames} jeux · ${parsed.consoles.size} consoles"
        buildChips()
        applyFilters()
    }

    private fun buildChips() {
        chips.removeAllViews()
        filter = "all"
        chips.addView(makeChip(getString(R.string.filter_all), "all"))
        for (console in consoles) {
            chips.addView(makeChip("${console.label} (${console.games.size})", console.id))
        }
        (chips.getChildAt(0) as? Chip)?.isChecked = true
    }

    private fun makeChip(label: String, id: String): Chip {
        val chip = Chip(this)
        chip.text = label
        chip.isCheckable = true
        chip.tag = id
        chip.setOnCheckedChangeListener { _, checked ->
            if (checked) {
                filter = id
                applyFilters()
            }
        }
        return chip
    }

    private fun applyFilters() {
        val needle = normalizeText(query.trim())
        val shown = ArrayList<Console>()
        for (console in consoles) {
            if (filter != "all" && console.id != filter) continue
            val games = if (needle.isEmpty()) {
                console.games
            } else {
                console.games.filter { game ->
                    normalizeText(game.title).contains(needle) ||
                        normalizeText(game.file).contains(needle)
                }
            }
            if (games.isEmpty()) continue
            shown.add(Console(console.id, console.label, games))
        }
        adapter.submit(shown)
    }

    private fun openGame(console: Console, game: Game) {
        GameSheet(this, prefs, roms, console, game, emulator) {
            adapter.notifyDataSetChanged()
        }.show()
    }

    private fun openSettings() {
        val before = prefs.siteUrl
        SettingsDialog(this, prefs, roms, emulator) {
            if (prefs.siteUrl != before) {
                library = null
                loadLibrary(force = true)
            } else {
                adapter.notifyDataSetChanged()
                updateStatus()
            }
        }.show()
    }

    // ------------------------------------------------------------- RetroArch

    private fun findEmulator() {
        emulator.packageName = Emulators.findRetroArch(this)
        if (emulator.packageName == null) return
        if (!receiverRegistered) {
            ContextCompat.registerReceiver(
                this,
                coresReceiver,
                IntentFilter(Emulators.ACTION_CORES_RESULT),
                ContextCompat.RECEIVER_EXPORTED
            )
            receiverRegistered = true
        }
        askCores()
    }

    /** Demande à RetroArch la liste de ses cores (deux essais, puis on laisse tomber). */
    private fun askCores() {
        val packageName = emulator.packageName ?: return
        if (emulator.coresKnown || coreAttempts >= 3) {
            updateStatus()
            return
        }
        coreAttempts += 1
        val intent = Intent(Emulators.ACTION_QUERY_CORES)
        intent.setPackage(packageName)
        sendBroadcast(intent)
        handler.postDelayed({ if (!emulator.coresKnown) askCores() else updateStatus() }, 1200)
    }

    // ------------------------------------------------------------- messages

    private fun updateStatus() {
        handler.removeCallbacks(resetStatus)
        statusLine.text = when {
            lastError != null -> "Hors ligne — $lastError"
            !StorageAccess.hasAccess(this) -> "Accès aux fichiers non accordé — Paramètres pour autoriser"
            emulator.packageName == null -> "RetroArch introuvable — installe-le pour lancer les jeux"
            emulator.coresKnown -> "RetroArch : ${emulator.cores.size} cores installés"
            else -> "RetroArch détecté — détection des cores…"
        }
    }

    /** Message court, effacé après quelques secondes. */
    private fun status(message: String) {
        statusLine.text = message
        handler.removeCallbacks(resetStatus)
        handler.postDelayed(resetStatus, 5000)
    }

    private companion object {
        const val CACHE_FILE = "library.json"
    }
}
