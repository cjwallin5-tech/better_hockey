# To do (as of 2026-10-20)

Feature ideas, aiming at a December launch. Check the code for what already exists before building any of these.

## Beating NHL.com (explain why, not just what)

1. **Luck and regression dashboard** (in progress): goals vs expected goals per skater, shooting % vs career norm, on-ice shooting and
   save % (PDO), and goals saved above expected for goalies. Label players as running hot or cold.
2. **Role changes:** flag power-play unit promotions/demotions and rises or drops in ice time over the last 5-10 games (we already
   store PP/EV/SH ice time per game and have a lines page).
3. **Rolling windows and game logs:** last 5, 10 and 20 games next to season totals, with a points-per-game trend line. Check what the
   player pages already show.
4. **Matchup quality:** opponent shots against and goals against, which goalie a team is likely to face, and a weekly strength-of-schedule score.

## Fantasy

5. **Value in your scoring:** rank every player by value above a replacement-level player under the league scoring you set.
6. **Trade analyzer:** enter "I give A and B, I get C" and compare using value above replacement, remaining schedule and the regression flags.
7. **Category league support** (H2H categories and roto): rank players by z-scores per category. The README only mentions points scoring.
8. **Streaming goalie finder:** goalies on weak weekly schedules who are likely to start, using the starter model.
9. **Digest upgrades:** add role-change and regression alerts to the morning email.

## Skipped on purpose

- Salary cap, contracts and real injury reports (not available from free NHL data; lineup gaps stay inferred).
- More EDGE speed and shot-speed features (fun trivia, doesn't predict fantasy results).
