package buzz.kirbytrim.mobile

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.os.Build
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
        "com.retroarch.aarch64", // RetroArch (AArch64) / RetroArch Plus
        "com.retroarch.ra32", // RetroArch (32 bits)
        "com.retroarch", // RetroArch (F-Droid)
        "org.retroarch", // paquet alternatif
        "com.retroarch64", // versions nightly
    )

    private const val ACTIVITY = "com.retroarch.browser.retroactivity.RetroActivityFuture"

    const val ACTION_QUERY_CORES = "com.retroarch.QUERY_INSTALLED_CORES"
    const val ACTION_CORES_RESULT = "com.retroarch.INSTALLED_CORES_RESULT"
    const val EXTRA_CORES = "CORES"

    /** Versions officielles (buildbot) : les seules qui lisent KirbyRetroROMs. */
    const val OFFICIAL_APK_ARM64 =
        "https://buildbot.libretro.com/stable/1.22.2/android/RetroArch_aarch64.apk"
    const val OFFICIAL_APK_ARM32 =
        "https://buildbot.libretro.com/stable/1.22.2/android/RetroArch_ra32.apk"

    /** Nom du paquet RetroArch installé, ou null. */
    fun findRetroArch(context: Context): String? {
        val manager = context.packageManager
        val installed = RETROARCH_PACKAGES.filter { packageInfo(manager, it) != null }
        // Si une version du Play Store et une version officielle cohabitent,
        // préférer celle qui peut réellement lire le dossier des ROMs.
        return installed.firstOrNull { canReadSharedStorage(context, it) } ?: installed.firstOrNull()
    }

    /**
     * Vrai si cette version de RetroArch peut lire le dossier des ROMs.
     *
     * Android 11+ : les versions publiées sur le Play Store n'ont accès qu'à leur
     * propre dossier — un jeu lancé depuis le launcher resterait noir. Les versions
     * officielles lisent le stockage partagé de deux façons : la permission « tous
     * les fichiers » (builds récents), ou le stockage « hérité » des applis qui
     * ciblent Android 10 ou moins — c'est le cas des versions 1.22 officielles.
     * Tout le reste est un build du Play Store.
     */
    fun canReadSharedStorage(context: Context, packageName: String): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return true
        val info = packageInfo(context.packageManager, packageName) ?: return true
        if (info.requestedPermissions
                ?.contains(Manifest.permission.MANAGE_EXTERNAL_STORAGE) == true) {
            return true
        }
        return (info.applicationInfo?.targetSdkVersion ?: 0) <= Build.VERSION_CODES.Q
    }

    /**
     * Vrai si RetroArch a déjà le droit de lire le stockage partagé.
     *
     * C'est RetroArch qui demande ce droit, et seulement au lancement de son menu
     * (l'appli launcher de RetroArch) : lancé directement sur une ROM, il ne le
     * demande pas — sans autorisation, le jeu s'ouvrirait sur un écran noir.
     */
    fun hasStorageAccess(context: Context, packageName: String): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return true
        val manager = context.packageManager
        val info = packageInfo(manager, packageName) ?: return true
        if (info.requestedPermissions
                ?.contains(Manifest.permission.MANAGE_EXTERNAL_STORAGE) == true) {
            // Builds récents : RetroArch montre lui-même la demande « tous les fichiers ».
            return true
        }
        return try {
            manager.checkPermission(Manifest.permission.READ_EXTERNAL_STORAGE, packageName) ==
                PackageManager.PERMISSION_GRANTED
        } catch (error: Exception) {
            true
        }
    }

    /** Nom affiché de l'appli (« RetroArch Plus »), pour les messages. */
    fun label(context: Context, packageName: String): String {
        val manager = context.packageManager
        val info = packageInfo(manager, packageName) ?: return packageName
        return try {
            manager.getApplicationLabel(info.applicationInfo).toString()
        } catch (error: Exception) {
            packageName
        }
    }

    /** Version officielle adaptée au téléphone (64 bits dans presque tous les cas). */
    fun officialApkUrl(): String =
        if (Build.SUPPORTED_64_BIT_ABIS.contains("arm64-v8a")) OFFICIAL_APK_ARM64 else OFFICIAL_APK_ARM32

    private fun packageInfo(manager: PackageManager, packageName: String): PackageInfo? = try {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            manager.getPackageInfo(
                packageName,
                PackageManager.PackageInfoFlags.of(PackageManager.GET_PERMISSIONS.toLong())
            )
        } else {
            @Suppress("DEPRECATION")
            manager.getPackageInfo(packageName, PackageManager.GET_PERMISSIONS)
        }
    } catch (error: PackageManager.NameNotFoundException) {
        null
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

    /**
     * Lancement direct d'une ROM dans RetroArch, avec le core choisi.
     *
     * Volontairement sans extra « CONFIGFILE » : c'est lui qui marque un lancement
     * « venu d'un launcher », et RetroArch saute alors sa propre demande d'accès aux
     * fichiers — sur un téléphone qui n'a jamais autorisé cet accès, le jeu s'ouvre
     * sur un écran noir. Sans cet extra, RetroArch pose la question lui-même.
     */
    fun launchIntent(packageName: String, romPath: String, coreFile: String?): Intent {
        val intent = Intent(Intent.ACTION_MAIN)
        intent.component = ComponentName(packageName, ACTIVITY)
        intent.addCategory(Intent.CATEGORY_LAUNCHER)
        intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        intent.putExtra("ROM", romPath)
        if (coreFile != null) intent.putExtra("LIBRETRO", corePath(packageName, coreFile))
        return intent
    }

    /**
     * Ouvre RetroArch sur son menu, sans jeu — comme un appui sur son icône.
     *
     * C'est le seul passage où RetroArch demande son autorisation d'accès aux
     * fichiers : une ROM arrivée d'un launcher ouvre le jeu directement.
     */
    fun menuIntent(context: Context, packageName: String): Intent {
        val fromLauncher = context.packageManager.getLaunchIntentForPackage(packageName)
        if (fromLauncher != null) {
            fromLauncher.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            return fromLauncher
        }
        val intent = Intent(Intent.ACTION_MAIN)
        intent.component = ComponentName(packageName, ACTIVITY)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
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
