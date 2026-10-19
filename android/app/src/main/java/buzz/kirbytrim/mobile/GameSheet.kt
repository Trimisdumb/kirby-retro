package buzz.kirbytrim.mobile

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.view.LayoutInflater
import android.view.View
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import coil.load
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.google.android.material.button.MaterialButton
import com.google.android.material.progressindicator.LinearProgressIndicator
import java.io.File

/**
 * Fiche d'un jeu : état du téléchargement, lecture dans RetroArch,
 * suppression, ouverture dans une autre appli.
 */
class GameSheet(
    private val activity: Activity,
    private val prefs: Prefs,
    private val roms: RomStore,
    private val console: Console,
    private val game: Game,
    private val emulator: EmulatorState,
    private val onChanged: () -> Unit,
) : BottomSheetDialog(activity) {

    private val handler = Handler(Looper.getMainLooper())

    private val cover: ImageView
    private val title: TextView
    private val meta: TextView
    private val coreLine: TextView
    private val stateLine: TextView
    private val progressRow: LinearLayout
    private val progress: LinearProgressIndicator
    private val progressText: TextView
    private val play: MaterialButton
    private val download: MaterialButton
    private val remove: MaterialButton
    private val openWith: MaterialButton
    private val hint: TextView

    private var task: RomDownload? = null
    private var attempts = 0
    private var afterDownload: ((File) -> Unit)? = null

    init {
        val view = LayoutInflater.from(activity).inflate(R.layout.sheet_game, null)
        setContentView(view)

        cover = view.findViewById(R.id.cover)
        title = view.findViewById(R.id.title)
        meta = view.findViewById(R.id.meta)
        coreLine = view.findViewById(R.id.core)
        stateLine = view.findViewById(R.id.state)
        progressRow = view.findViewById(R.id.progress_row)
        progress = view.findViewById(R.id.progress)
        progressText = view.findViewById(R.id.progress_text)
        play = view.findViewById(R.id.play)
        download = view.findViewById(R.id.download)
        remove = view.findViewById(R.id.delete)
        openWith = view.findViewById(R.id.open_with)
        hint = view.findViewById(R.id.hint)

        play.setOnClickListener { onPlay() }
        download.setOnClickListener { startDownload() }
        remove.setOnClickListener { confirmDelete() }
        openWith.setOnClickListener { onOpenWith() }

        bind()
    }

    private fun bind() {
        val rom = roms.fileFor(game.system, game.file)
        val downloaded = rom.isFile

        if (game.cover != null) cover.load(game.cover)
        title.text = game.title

        val bits = ArrayList<String>()
        bits.add(console.label)
        bits.add(formatSize(game.size))
        game.region?.let(bits::add)
        game.year?.let(bits::add)
        meta.text = bits.joinToString(" · ")

        coreLine.text = describeCore()
        stateLine.text = activity.getString(
            if (downloaded) R.string.state_downloaded else R.string.state_missing
        )
        hint.text = "RetroArch lit la ROM depuis « ${prefs.romsDir} »."
        setBusy(false)
    }

    /** Ce qui sera utilisé comme core au lancement. */
    private fun describeCore(): String {
        if (prefs.letRetroarchChooseCore) return "Core : choisi par RetroArch"
        prefs.coreOverride(console.id)?.let { file ->
            return "Core : ${Emulators.coreName(file)} (choisi à la main)"
        }
        if (!emulator.coresKnown) return "Core : en attente de la réponse de RetroArch"
        val known = Emulators.installedCoresFor(console.id, emulator.cores).firstOrNull()
        if (known != null) return "Core : $known"
        return if (emulator.cores.isEmpty()) {
            "Core : aucun core installé dans RetroArch"
        } else {
            "Core : à choisir (aucun core conseillé n'est installé)"
        }
    }

    private fun setBusy(busy: Boolean) {
        val downloaded = roms.exists(game.system, game.file)
        play.isEnabled = !busy
        download.isEnabled = !busy && !downloaded
        remove.isEnabled = !busy && downloaded
        openWith.isEnabled = !busy
    }

    // ------------------------------------------------------------- lecture

    private fun onPlay() {
        if (task != null) return
        if (!StorageAccess.hasAccess(activity)) {
            StorageAccess.requestAccess(activity)
            toast(activity.getString(R.string.need_access))
            return
        }
        val rom = roms.fileFor(game.system, game.file)
        if (rom.isFile) launch(rom) else startDownload { file -> launch(file) }
    }

    private fun launch(rom: File) {
        val packageName = Emulators.findRetroArch(activity)
        if (packageName == null) {
            emulator.packageName = null
            askInstallRetroArch()
            return
        }
        emulator.packageName = packageName

        if (prefs.letRetroarchChooseCore) {
            start(packageName, rom, null)
            return
        }
        prefs.coreOverride(console.id)?.let { file ->
            start(packageName, rom, file)
            return
        }
        if (emulator.coresKnown) {
            if (emulator.cores.isEmpty()) {
                tellNoCoreInstalled(packageName)
                return
            }
            val known = Emulators.installedCoresFor(console.id, emulator.cores).firstOrNull()
            if (known == null) {
                pickCore(packageName, rom)
                return
            }
            start(packageName, rom, Emulators.fileForCore(emulator.cores, known))
            return
        }
        // Aucune réponse de RetroArch : on tente le core conseillé.
        val guess = androidCores(console.id).firstOrNull()
        start(packageName, rom, guess?.let { it + "_libretro_android.so" })
    }

    private fun start(packageName: String, rom: File, coreFile: String?) {
        try {
            activity.startActivity(Emulators.launchIntent(packageName, rom.absolutePath, coreFile))
            dismiss()
        } catch (error: ActivityNotFoundException) {
            launchFailed("RetroArch ($packageName) a refusé le lancement")
        } catch (error: Exception) {
            launchFailed(error.message ?: error.javaClass.simpleName)
        }
    }

    private fun launchFailed(reason: String) {
        AlertDialog.Builder(activity)
            .setTitle("Lancement impossible")
            .setMessage("$reason\n\nTu peux ouvrir la ROM dans une autre appli installée sur le téléphone.")
            .setPositiveButton(R.string.button_open_with) { _, _ -> onOpenWith() }
            .setNegativeButton(R.string.button_close, null)
            .show()
    }

    private fun askInstallRetroArch() {
        AlertDialog.Builder(activity)
            .setTitle("RetroArch n'est pas installé")
            .setMessage(
                "Le launcher lance les jeux dans RetroArch, comme sur PC : " +
                    "installe RetroArch (ou RetroArch Plus), puis reviens."
            )
            .setPositiveButton("Installer RetroArch") { _, _ -> openStore() }
            .setNeutralButton(R.string.button_open_with) { _, _ -> onOpenWith() }
            .setNegativeButton(R.string.button_close, null)
            .show()
    }

    private fun tellNoCoreInstalled(packageName: String) {
        AlertDialog.Builder(activity)
            .setTitle("Aucun core dans RetroArch")
            .setMessage(
                "RetroArch n'a aucun core installé : ouvre RetroArch → " +
                    "« Charger un contenu » → « Télécharger un core », installe par exemple " +
                    "« ${androidCores(console.id).firstOrNull() ?: "un core pour cette console"} », puis reviens."
            )
            .setPositiveButton("Ouvrir RetroArch") { _, _ -> openRetroArch(packageName) }
            .setNegativeButton(R.string.button_close, null)
            .show()
    }

    /** Choisit un core parmi ceux installés (retenu pour cette console). */
    private fun pickCore(packageName: String, rom: File) {
        val files = emulator.cores
        val labels = ArrayList<String>(files.size + 1)
        labels.add(activity.getString(R.string.core_auto))
        for (file in files) labels.add(Emulators.coreName(file))
        AlertDialog.Builder(activity)
            .setTitle(activity.getString(R.string.core_pick_title, console.label))
            .setItems(labels.toTypedArray()) { _, index ->
                val chosen = if (index == 0) null else files[index - 1]
                prefs.setCoreOverride(console.id, chosen)
                bind()
                onChanged()
                start(packageName, rom, chosen)
            }
            .setNegativeButton(R.string.button_cancel, null)
            .show()
    }

    private fun openStore() {
        try {
            activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(Emulators.STORE_URL)))
        } catch (error: ActivityNotFoundException) {
            toast("Magasin d'applications introuvable")
        }
    }

    private fun openRetroArch(packageName: String) {
        try {
            activity.startActivity(Emulators.menuIntent(packageName))
        } catch (error: Exception) {
            toast("RetroArch n'a pas répondu")
        }
    }

    private fun onOpenWith() {
        val rom = roms.fileFor(game.system, game.file)
        if (!rom.isFile) {
            toast(activity.getString(R.string.download_first))
            return
        }
        try {
            val intent = Intent.createChooser(
                Emulators.openWithIntent(activity, rom),
                activity.getString(R.string.button_open_with)
            )
            activity.startActivity(intent)
        } catch (error: IllegalArgumentException) {
            toast("Dossier des ROMs hors du stockage partagé : ouverture impossible")
        } catch (error: ActivityNotFoundException) {
            toast("Aucune appli ne peut ouvrir cette ROM")
        }
    }

    // ------------------------------------------------------- téléchargement

    private fun startDownload(after: ((File) -> Unit)? = null) {
        if (task != null) return
        if (!StorageAccess.hasAccess(activity)) {
            StorageAccess.requestAccess(activity)
            toast(activity.getString(R.string.need_access))
            return
        }
        afterDownload = after
        attempts = 0
        beginDownload()
    }

    private fun beginDownload() {
        val rom = roms.fileFor(game.system, game.file)
        val url = Site.romUrl(prefs.siteUrl, game.system, game.file)
        progressRow.visibility = View.VISIBLE
        progress.isIndeterminate = true
        progressText.text = ""
        setBusy(true)
        val started = RomDownload(url, rom, object : RomDownload.Listener {
            override fun onProgress(read: Long, total: Long) {
                handler.post { showProgress(read, total) }
            }

            override fun onFinished(file: File) {
                handler.post { finishDownload(file) }
            }

            override fun onFailed(error: Exception) {
                handler.post { failDownload(error) }
            }
        })
        task = started
        started.start()
    }

    private fun showProgress(read: Long, total: Long) {
        if (total > 0) {
            progress.isIndeterminate = false
            progress.max = 1000
            progress.progress = ((read * 1000) / total).toInt()
            progressText.text = "${read * 100 / total} %"
        } else {
            progressText.text = formatSize(read)
        }
    }

    private fun finishDownload(file: File) {
        val after = afterDownload
        task = null
        afterDownload = null
        progressRow.visibility = View.GONE
        bind()
        onChanged()
        toast(activity.getString(R.string.downloaded, file.name))
        after?.invoke(file)
    }

    private fun failDownload(error: Exception) {
        task = null
        if (error is InterruptedException) {
            progressRow.visibility = View.GONE
            setBusy(false)
            return
        }
        if (attempts < MAX_ATTEMPTS) {
            attempts += 1
            progressText.text = "nouvelle tentative…"
            handler.postDelayed({ beginDownload() }, 1500)
            return
        }
        afterDownload = null
        progressRow.visibility = View.GONE
        setBusy(false)
        toast("Téléchargement impossible : ${error.message ?: error.javaClass.simpleName}")
    }

    private fun confirmDelete() {
        val rom = roms.fileFor(game.system, game.file)
        if (!rom.isFile) {
            toast("Rien à supprimer")
            return
        }
        AlertDialog.Builder(activity)
            .setTitle(game.title)
            .setMessage("Supprimer la ROM du téléphone (${formatSize(rom.length())}) ?")
            .setPositiveButton(R.string.button_delete) { _, _ ->
                if (rom.delete()) {
                    bind()
                    onChanged()
                    toast("ROM supprimée")
                } else {
                    toast("Suppression impossible")
                }
            }
            .setNegativeButton(R.string.button_cancel, null)
            .show()
    }

    override fun dismiss() {
        task?.cancel()
        task = null
        afterDownload = null
        super.dismiss()
    }

    private fun toast(message: String) {
        Toast.makeText(activity, message, Toast.LENGTH_SHORT).show()
    }

    private companion object {
        const val MAX_ATTEMPTS = 2
    }
}
