package buzz.kirbytrim.mobile

import android.Manifest
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import java.io.File

/** Dossier des ROMs : chemins, présence des fichiers, suppression. */
class RomStore(private val prefs: Prefs) {

    fun dir(): File = File(prefs.romsDir)

    /** Comme le launcher PC : <dossier>/<console>/<fichier>. */
    fun fileFor(system: String, fileName: String): File = File(File(dir(), system), fileName)

    fun exists(system: String, fileName: String): Boolean = fileFor(system, fileName).isFile

    fun delete(system: String, fileName: String): Boolean = fileFor(system, fileName).delete()
}

/**
 * Accès au stockage partagé : les ROMs doivent être lisibles par RetroArch,
 * donc écrites à la racine du stockage, pas dans les données privées de l'appli.
 */
object StorageAccess {

    fun hasAccess(context: Context): Boolean =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Environment.isExternalStorageManager()
        } else {
            ContextCompat.checkSelfPermission(context, Manifest.permission.WRITE_EXTERNAL_STORAGE) ==
                PackageManager.PERMISSION_GRANTED
        }

    /** Ouvre les réglages « tous les fichiers » (Android 11+) ou demande la permission. */
    fun requestAccess(activity: Activity) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val intent = Intent(
                Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                Uri.parse("package:${activity.packageName}")
            )
            try {
                activity.startActivity(intent)
                return
            } catch (error: ActivityNotFoundException) {
                // Certains téléphones n'ont que l'écran global des réglages.
            }
            try {
                activity.startActivity(Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION))
            } catch (error: ActivityNotFoundException) {
                requestLegacy(activity)
            }
        } else {
            requestLegacy(activity)
        }
    }

    private fun requestLegacy(activity: Activity) {
        ActivityCompat.requestPermissions(
            activity,
            arrayOf(Manifest.permission.WRITE_EXTERNAL_STORAGE, Manifest.permission.READ_EXTERNAL_STORAGE),
            REQUEST_CODE
        )
    }

    private const val REQUEST_CODE = 42
}
