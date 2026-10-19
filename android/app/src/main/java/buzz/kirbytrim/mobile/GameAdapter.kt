package buzz.kirbytrim.mobile

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import coil.load

/** Grille de jeux : jaquette, titre, console, pastille « téléchargé ». */
class GameAdapter(private val onTap: (Console, Game) -> Unit) :
    RecyclerView.Adapter<GameAdapter.Holder>() {

    private val rows = ArrayList<Row>()

    class Row(val console: Console, val game: Game)

    /** Vrai si la ROM est déjà sur le téléphone (relu à chaque affichage). */
    var isDownloaded: (Game) -> Boolean = { false }

    fun submit(consoles: List<Console>) {
        rows.clear()
        for (console in consoles) {
            for (game in console.games) rows.add(Row(console, game))
        }
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder {
        val view = LayoutInflater.from(parent.context).inflate(R.layout.item_game, parent, false)
        return Holder(view, onTap)
    }

    override fun getItemCount(): Int = rows.size

    override fun onBindViewHolder(holder: Holder, position: Int) {
        val row = rows[position]
        holder.bind(row, isDownloaded(row.game))
    }

    inner class Holder(private val view: View, private val onTap: (Console, Game) -> Unit) :
        RecyclerView.ViewHolder(view) {

        private val cover: ImageView = view.findViewById(R.id.cover)
        private val title: TextView = view.findViewById(R.id.title)
        private val meta: TextView = view.findViewById(R.id.meta)
        private val badge: TextView = view.findViewById(R.id.badge)

        fun bind(row: Row, downloaded: Boolean) {
            title.text = row.game.title
            meta.text = row.console.label
            badge.visibility = if (downloaded) View.VISIBLE else View.GONE
            if (row.game.cover != null) cover.load(row.game.cover) else cover.setImageDrawable(null)
            view.setOnClickListener { onTap(row.console, row.game) }
        }
    }
}
