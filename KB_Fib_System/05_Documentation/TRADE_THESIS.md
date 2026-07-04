# Trade Thesis — Why the KB Fib Dual Trade Works

The reasoning behind the mechanics. The rules say *what* to do; this says *why*, so you can judge
when the edge is present and when a setup is just noise.

---

## The core idea

After a sharp **A→B down-swing**, price rarely recovers in a straight line. It tends to retrace a
*measurable* fraction of the drop before deciding its next move. The Fibonacci golden zone
(0.618–0.68) is the retracement band where, historically, decisions cluster: either price stalls and
rolls over, or it pushes through and the move continues. The strategy positions around that decision
point twice — once on the way into the zone (Trade 1) and once on the way out the top of it
(Trade 2).

## Why two trades from one swing

A single A→B drop encodes more than one opportunity:

- **Trade 1** is the *retracement-continuation* play: buy the dip into 0.32–0.382 (a shallow,
  early retracement), target the golden zone. This is the higher-probability, smaller-reward leg.
- **Trade 2** is the *breakout* play: if price reaches and pushes *through* the golden zone
  (0.68), the retracement has become a trend reversal; ride it toward full retracement (1.0). Lower
  probability, larger reward.

Stacking them means one piece of analysis (find the A→B, draw the fibs) funds two distinct
risk/reward profiles. The 0.618–0.68 band doing double duty (T1 exit = T2 entry) is what makes the
structure clean rather than two unrelated trades.

## Why the confluence filters matter

A fib level alone is a line on a chart — lots of price touches it and nothing happens. The filters
exist to demand that *other things agree* before committing:

- **EMA 9 & EMA 21:** require price to be above both, i.e. short-term momentum has actually turned
  up, not just touched a level. Filters out catching a falling knife.
- **Volume > 1.2× average:** require participation behind the move. A breakout on thin volume is
  suspect; the filter insists real money is involved.

The thesis is explicitly **confluence-based**: fib location + momentum (EMA) + participation
(volume), all three, before an entry counts. Remove a filter and you're trading a weaker signal.

## Why "first touch" for take-profit

TP fires when price *touches* the target zone, not when it closes beyond it. The thesis: the zone is
where reactions happen, so the edge is in being out (or rotating to T2) *as* price reaches it, before
the potential rejection — not waiting for confirmation that arrives too late. This trades a bit of
upside for a higher realized hit rate. (Flagged in the rules doc as worth measuring against a
close-based alternative.)

## Why daily, NSE

The swings are cleanest and the fib retracement behavior most reliable on the **daily timeframe**,
where a single bar is a full session of conviction rather than intraday noise. NSE equities are the
chosen universe because that's the market being traded and where the operator has context. Lower
timeframes (4H/1H/15m) work but need a lower ZigZag deviation and produce noisier setups.

## What the scanner adds to the thesis

The chart proves the idea on one name. The scanner asks: *across all 500 names, who is right now at
a decision point?* It turns a discretionary chart pattern into a daily shortlist — surfacing
Approaching / In Zone / Triggered candidates so attention goes only to names where the setup is
actually live. It does not change the thesis; it scales the search for it.

## The honest limits of the thesis

- It's a **mean-reversion-then-continuation** bet. In a violently trending market with no clean
  retracements, setups will be sparse or fail.
- Fib levels are **self-fulfilling to a degree** (many traders watch them) but not magic — the
  filters exist precisely because the levels alone aren't enough.
- The biggest open question (see rules §10) is whether the realized hit rate justifies the
  first-touch TP and the down-swing-only restriction. Until real outcomes are logged, the thesis is
  reasoned, not yet proven on your own data.
