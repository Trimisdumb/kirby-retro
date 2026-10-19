package buzz.kirbytrim.mobile

import android.content.Context
import android.os.Environment
import java.io.File

/** Réglages de l'appli : site, dossier des ROMs, cores choisis à la main. */
class Prefs(context: Context) {

    private val store = context.getSharedPreferences("kirby-retro", Context.MODE_PRIVATE)

    /** Adresse du site (sans « / » final). */
    var siteUrl: String
        get() = store.getString("siteUrl", null)?.takeIf { it.isNotBlank() } ?: DEFAULT_SITE
        set(value) {
            val clean = value.trim().trimEnd('/')
            store.edit().putString("siteUrl", clean.ifBlank { DEFAULT_SITE }).apply()
        }

    /** Dossier où sont téléchargées les ROMs (visible par RetroArch). */
    var romsDir: String
        get() = store.getString("romsDir", null)?.takeIf { it.isNotBlank() } ?: defaultRomsDir()
        set(value) {
            val clean = value.trim()
            store.edit().putString("romsDir", clean.ifBlank { defaultRomsDir() }).apply()
        }

    /** Dernière adresse de site dont la bibliothèque a été mise en cache. */
    var cacheSite: String?
        get() = store.getString("cacheSite", null)
        set(value) = store.edit().putString("cacheSite", value).apply()

    /** Laisser RetroArch choisir son core (aucun core imposé au lancement). */
    var letRetroarchChooseCore: Boolean
        get() = store.getBoolean("coreAuto", false)
        set(value) = store.edit().putBoolean("coreAuto", value).apply()

    /** Core imposé pour une console, choisi dans la liste des cores installés. */
    fun coreOverride(system: String): String? = store.getString("core:$system", null)

    fun setCoreOverride(system: String, core: String?) {
        val editor = store.edit()
        if (core == null) editor.remove("core:$system") else editor.putString("core:$system", core)
        editor.apply()
    }

    fun hasCoreOverrides(): Boolean = store.all.keys.any { it.startsWith("core:") }

    /** Oublie tous les cores choisis à la main. */
    fun clearCoreOverrides(): Int {
        val keys = store.all.keys.filter { it.startsWith("core:") }
        val editor = store.edit()
        for (key in keys) editor.remove(key)
        editor.apply()
        return keys.size
    }

    companion object {
        const val DEFAULT_SITE = "https://retro.kirbytrim.buzz"

        /** Comme sur PC (~/KirbyRetroROMs), mais dans le stockage du téléphone. */
        fun defaultRomsDir(): String =
            File(Environment.getExternalStorageDirectory(), "KirbyRetroROMs").absolutePath
    }
}
