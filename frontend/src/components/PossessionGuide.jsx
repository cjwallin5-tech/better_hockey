import { Link } from 'react-router-dom'

/**
 * A plain-language guide to the possession stats (Corsi, Fenwick, expected goals, PDO), as a collapsed panel so it costs a line of space
 * for people who know them and answers the question for people who don't. `open` starts it expanded.
 */
export default function PossessionGuide({ open = false }) {
  return (
    <details className="guide" open={open}>
      <summary>New to possession stats? What they mean</summary>
      <div className="guide-body">
        <p className="guide-lead">
          Possession stats ask one question: <strong>while this player is on the ice, which team has the puck more?</strong> The team that
          shoots more usually has it more, and over a season that tends to lead to more goals. They are counted at five-on-five (no power
          plays), so every player is judged on the same kind of hockey.
        </p>
        <dl>
          <div>
            <dt><Link to="/glossary#corsi">Corsi (CF%)</Link></dt>
            <dd>
              Counts every shot attempt: shots on goal, misses and blocked shots. <strong>CF%</strong> is your team's share of all the attempts
              while the player is on the ice. Example: the team takes 55 attempts and the other team takes 45, so CF% is 55 / (55 + 45) = 55%.
              <em>50% is even; above 50% means the team is out-shooting its opponent with him on the ice.</em>
            </dd>
          </div>
          <div>
            <dt><Link to="/glossary#fenwick">Fenwick (FF%)</Link></dt>
            <dd>The same as Corsi but leaving out blocked shots, which some people feel measure effort more than quality.</dd>
          </div>
          <div>
            <dt><Link to="/glossary#relative">Rel (relative)</Link></dt>
            <dd>
              Corsi with him on the ice minus Corsi with him off it. It shows whether the team does better or worse because of this player,
              which matters on a strong or weak team. <em>Plus is good, minus is bad.</em>
            </dd>
          </div>
          <div>
            <dt><Link to="/glossary#xg">Expected goals (xG, xGF%)</Link></dt>
            <dd>
              Not every shot is equal: a shot from the slot is worth more than one from the boards. Our own model gives each shot a chance of
              scoring and adds them up. <strong>ixG</strong> is a player's own, and <strong>xGF%</strong> is his team's share of the expected
              goals while he is on the ice. <strong>G − ixG</strong> is goals scored minus goals expected: positive means finishing above the chances.
            </dd>
          </div>
          <div>
            <dt><Link to="/glossary#pdo">PDO</Link></dt>
            <dd>
              The team's shooting percentage plus its save percentage while he is on the ice. It tends to drift back toward 100, so a number far
              above 100 often means good luck, far below means bad luck.
            </dd>
          </div>
        </dl>
        <p className="guide-foot">
          Treat these as clues, not verdicts. Linemates, who a player faces and where shifts start all matter, and early in the season the
          numbers swing a lot (the page dims them until there are enough games). Most regulars land between about 45% and 55%.
          {' '}<Link to="/glossary">See every definition in the glossary</Link>.
        </p>
      </div>
    </details>
  )
}
