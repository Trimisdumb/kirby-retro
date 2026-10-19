package buzz.kirbytrim.mobile

import android.app.Activity
import android.view.LayoutInflater
import android.view.View
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.widget.SwitchCompat
import com.google.android.material.button.MaterialButton
import com.google.android.material.textfield.TextInputEditText

/** Fenêtre « Paramètres » : site, dossier des ROMs, accès aux fichiers, cores. */
class SettingsDialog(
    private val activity: Activity,
    private val prefs: Prefs,
    private val roms: RomStore,
    private val emulator: EmulatorState,
    private val onSaved: () -> Unit,
) {

    private lateinit var dialog: AlertDialog

    fun show() {
        val view = LayoutInflater.from(activity).inflate(R.layout.dialog_settings, null)
        val site = view.findViewById<TextInputEditText>(R.id.site)
        val romsField = view.findViewById<TextInputEditText>(R.id.roms)
        val coreAuto = view.findViewById<SwitchCompat>(R.id.core_auto)
        val state = view.findViewById<TextView>(R.id.state)
        val access = view.findViewById<MaterialButton>(R.id.access)
        val reset = view.findViewById<MaterialButton>(R.id.reset_cores)

        site.setText(prefs.siteUrl)
        romsField.setText(prefs.romsDir)
        coreAuto.isChecked = prefs.letRetroarchChooseCore
        state.text = describeState()
        access.visibility = if (StorageAccess.hasAccess(activity)) View.GONE else View.VISIBLE
        reset.visibility = if (prefs.hasCoreOverrides()) View.VISIBLE else View.GONE

        access.setOnClickListener {
            StorageAccess.requestAccess(activity)
            dialog.dismiss()
            toast("Autorise l'accès, puis reviens dans Paramètres")
        }
        reset.setOnClickListener {
            val count = prefs.clearCoreOverrides()
            toast("$count core(s) oublié(s)")
            dialog.dismiss()
        }

        dialog = AlertDialog.Builder(activity)
            .setTitle(R.string.settings_title)
            .setView(view)
            .setPositiveButton(R.string.button_save) { _, _ -> save(site, romsField, coreAuto) }
            .setNegativeButton(R.string.button_cancel, null)
            .create()
        dialog.show()
    }

    private fun save(site: TextInputEditText, romsField: TextInputEditText, coreAuto: SwitchCompat) {
        prefs.siteUrl = site.text?.toString().orEmpty()
        prefs.romsDir = romsField.text?.toString().orEmpty()
        prefs.letRetroarchChooseCore = coreAuto.isChecked
        try {
            roms.dir().mkdirs()
        } catch (error: Exception) {
            // Le dossier sera créé au premier téléchargement.
        }
        onSaved()
    }

    private fun describeState(): String {
        val lines = ArrayList<String>()
        val packageName = Emulators.findRetroArch(activity)
        emulator.packageName = packageName
        lines.add(
            when {
                packageName == null ->
                    "RetroArch : introuvable — installe RetroArch officiel pour lancer les jeux"
                !Emulators.canReadSharedStorage(activity, packageName) ->
                    "RetroArch : ${Emulators.label(activity, packageName)} — version du Play " +
                        "Store, ne peut pas lire les ROMs (écran noir au lancement)"
                !Emulators.hasStorageAccess(activity, packageName) ->
                    "RetroArch : ${Emulators.label(activity, packageName)} — accès aux " +
                        "fichiers à autoriser (ouvre RetroArch depuis son icône)"
                else -> "RetroArch : ${Emulators.label(activity, packageName)}"
            }
        )
        lines.add(
            when {
                emulator.coresKnown -> "Cores installés : ${emulator.cores.size}"
                packageName == null -> "Cores : —"
                else -> "Cores : pas encore de réponse de RetroArch"
            }
        )
        lines.add(
            if (StorageAccess.hasAccess(activity)) {
                "Accès aux fichiers : accordé"
            } else {
                "Accès aux fichiers : à autoriser (RetroArch doit pouvoir lire les ROMs)"
            }
        )
        lines.add("Dossier des ROMs : ${prefs.romsDir}")
        return lines.joinToString("\n")
    }

    private fun toast(message: String) {
        Toast.makeText(activity, message, Toast.LENGTH_SHORT).show()
    }
}
