package buzz.kirbytrim.mobile

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Environment
import androidx.core.content.FileProvider
import java.io.File

/** Ce que l'appli sait de RetroArch : paquet trouvé, cores installés. */
class EmulatorState {
    var packageName: String? = null
    var cores: List<String> = emptyList()

    /** Vrai quand RetroArch a répondu à la question « quels cores ? ». */
    var coresKnown = false
}

/**
 * RetroArch Android : détection, cores installés, lancement direct d'un jeu.
 *
 * RetroArch accepte un lancement explicite (activité RetroActivityFuture) avec
 * les extras « ROM » et « LIBRETRO » — c'est ce que font les frontends Android.
 * Il sait aussi énumérer ses cores par diffusion (InstalledCoresReceiver).
 */
object Emulators {

    /** Paquets RetroArch connus, par ordre de préférence. */
    private val RETROARCH_PACKAGES = listOf(
        "com.retroarch.aarch64", // RetroArch Plus (64 bits)
        "com.retroarch.ra32", // RetroArch 32 bits
        "com.retroarch", // RetroArch (Play Store, F-Droid)
        "org.retroarch", // paquet alternatif
        "com.retroarch64", // versions nightly
    )

    private const val ACTIVITY = "com.retroarch.browser.retroactivity.RetroActivityFuture"

    const val ACTION_QUERY_CORES = "com.retroarch.QUERY_INSTALLED_CORES"
    const val ACTION_CORES_RESULT = "com.retroarch.INSTALLED_CORES_RESULT"
    const val EXTRA_CORES = "CORES"

    const val STORE_URL = "https://play.google.com/store/apps/details?id=com.retroarch.aarch64"

    /** Nom du paquet RetroArch installé, ou null. */
    fun findRetroArch(context: Context): String? {
        val manager = context.packageManager
        return RETROARCH_PACKAGES.firstOrNull { packageName -> isInstalled(manager, packageName) }
    }

    private fun isInstalled(manager: PackageManager, packageName: String): Boolean = try {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            manager.getPackageInfo(packageName, PackageManager.PackageInfoFlags.of(0))
        } else {
            @Suppress("DEPRECATION")
            manager.getPackageInfo(packageName, 0)
        }
        true
    } catch (error: PackageManager.NameNotFoundException) {
        false
    }

    /** « snes9x_libretro_android.so » → « snes9x ». */
    fun coreName(coreFile: String): String = coreFile
        .removeSuffix(".so")
        .removeSuffix("_android")
        .removeSuffix("_libretro")

    /** Fichier installé qui correspond à un core connu. */
    fun fileForCore(installed: List<String>, name: String): String? =
        installed.firstOrNull { coreName(it) == name }

    /** Cores conseillés pour cette console qui sont réellement installés. */
    fun installedCoresFor(system: String, installed: List<String>): List<String> =
        androidCores(system).filter { wanted -> installed.any { coreName(it) == wanted } }

    /** Chemin du core dans les données privées de RetroArch (lu par RetroArch seul). */
    fun corePath(packageName: String, coreFile: String): String =
        "/data/data/$packageName/cores/$coreFile"

    /** Lancement direct d'une ROM dans RetroArch, avec le core choisi. */
    fun launchIntent(packageName: String, romPath: String, coreFile: String?): Intent {
        val intent = Intent(Intent.ACTION_MAIN)
        intent.component = ComponentName(packageName, ACTIVITY)
        intent.addCategory(Intent.CATEGORY_LAUNCHER)
        intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        intent.putExtra("ROM", romPath)
        if (coreFile != null) intent.putExtra("LIBRETRO", corePath(packageName, coreFile))
        // Avec ce fichier de config, RetroArch reconnaît un lancement « venu d'un launcher ».
        val config = File(
            Environment.getExternalStorageDirectory(),
            "Android/data/$packageName/files/retroarch.cfg"
        )
        intent.putExtra("CONFIGFILE", config.absolutePath)
        return intent
    }

    /** Ouvre RetroArch sur son menu, sans jeu. */
    fun menuIntent(packageName: String): Intent {
        val intent = Intent(Intent.ACTION_MAIN)
        intent.component = ComponentName(packageName, ACTIVITY)
        intent.addCategory(Intent.CATEGORY_LAUNCHER)
        intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
        return intent
    }

    /** « Ouvrir avec… » : n'importe quel émulateur installé peut prendre la ROM. */
    fun openWithIntent(context: Context, rom: File): Intent {
        val uri = FileProvider.getUriForFile(context, context.packageName + ".files", rom)
        val intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(uri, "application/octet-stream")
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        return intent
    }
}
