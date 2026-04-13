"""Historical crisis context injected into prediction model prompts.

Claude's training data cuts off ~August 2025. The Iran-Hormuz crisis began
February 2026. Without this context, the models are predicting blind about
events they have zero knowledge of. This module provides a structured timeline
that gets prepended to every prediction prompt.

Update this document as events unfold.
Last updated: 2026-04-12
"""

CRISIS_TIMELINE = """
## CRITICAL CONTEXT — You must read this carefully before making any predictions.

Your training data ends around August 2025. The following events have occurred
AFTER your knowledge cutoff. This is not hypothetical — these are real events
that have already happened.

### Background: 2025 Iran-US Tensions
- Mid-2025: Failed nuclear negotiations between Iran and the US in Geneva.
- June 2025: Brief 12-day US air conflict with Iran. Oil markets shrugged it
  off — Brent stayed below $70. Iran's Strait of Hormuz remained open.
- Late 2025: Tensions continued to escalate. Iran accelerated uranium
  enrichment.

### February 2026: War Begins
- Feb 6: Iran and US held indirect nuclear talks in Oman's capital Muscat.
- Feb 15-20: Iran tripled oil exports and drew down storage, anticipating
  disruption.
- Feb 27: Omani FM announced a "breakthrough" — Iran agreed to halt enriched
  uranium stockpiling and accept IAEA verification.
- **Feb 28: US and Israel launched coordinated air strikes across Iran. Supreme
  Leader Ali Khamenei was killed.** Iran retaliated with missiles and drones on
  Israel, US bases, and Gulf allies.
- **Feb 28: Iran announced closure of Strait of Hormuz in retaliation.** IRGC
  began attacking merchant ships and laying sea mines.

### March 2026: Hormuz Blockade & Oil Shock
- Mar 2: IRGC officially confirmed Strait of Hormuz closed. Threatened to set
  fire to any ship entering. Brent crude surged from ~$72 to $82 (+13%).
- Mar 4: Strait fully blocked. Oil/LNG exports stranded. Brent broke $120.
- Mar 9: Brent hit $119.50 session high. WTI posted biggest weekly gain in
  history (+35.6%). Trump falsely claimed strait had reopened.
- Mar 15: Trump demanded NATO and China help reopen the strait.
- Mar 19: US began aerial campaign against Iranian naval targets to forcibly
  reopen Hormuz.
- Mar 21: Trump issued 48-hour ultimatum to Iran. Iran doubled down, threatening
  to strike Gulf desalination plants and power infrastructure.
- Mar 23: Oil dropped ~11% after Trump paused strikes on Iran energy
  infrastructure for 5 days.
- Mar 25: Pakistan delivered US "15-point proposal" to Iran: end nuclear program,
  reopen Hormuz, limit missiles, restrict armed groups, in exchange for sanctions
  relief. Iran rejected it.
- Mar 26-27: Israeli airstrike killed IRGC Navy Commander Tangsiri (directly
  responsible for Hormuz closure).
- Mar 28: Houthis entered the war — launched ballistic missile toward Israel.
  2,500 US Marines deployed for Hormuz operations.
- Mar 31: Kuwaiti VLCC Al Salmi struck by Iranian drone at Port of Dubai. WSJ:
  Trump admin concludes military Hormuz reopening would take too long — shifting
  to diplomacy. Brent-WTI spread peaked at $25/bbl.

### April 2026: Ceasefire & Fragile Negotiations
- Apr 1: Trump claims Iran requested ceasefire — Iran FM calls it "false."
- Apr 2: UK-led 40-nation conference on Hormuz. Iran tightens blockade further,
  drops shipping to 10-20 ships/day from 150.
- **Apr 3: US F-15E shot down over Iran (pilot rescued, WSO missing 48hrs).
  Second US plane crashes near Hormuz. Iran hits Gulf refineries.** War costs
  becoming tangible for the US. Brent $112.
- **Apr 4: Trump issues 48-hour ultimatum: "all Hell will reign down." Israel
  strikes Iran's largest petrochemical complex at Asaluyeh (inoperable).**
- **Apr 5: Iran retaliates — strikes BAPCO oil refinery in Bahrain, drones hit
  Kuwaiti power/desalination plants. 45-day ceasefire proposed by mediators;
  Iran REJECTS it, demanding permanent end to war.**
- Apr 6: Iran FM: "We won't merely accept a ceasefire." Trump: deadline is
  "final." Brent $111.
- **Apr 7: CEASEFIRE AGREED 2 hours before Trump's deadline.** Dated Brent hit
  ALL-TIME RECORD $144.42 BEFORE announcement, then crashed 13% to ~$95. At
  least 50 new Polymarket accounts made large ceasefire bets minutes before
  — suspected insider trading.
- **Apr 8: Ceasefire in effect BUT Israel strikes Lebanon same day. Iran calls it
  "grave violation." Little Hormuz reopening.** Dated Brent spot $124.68 vs
  futures $93.76 — massive physical/paper divergence.
- **Apr 9: Hormuz remains "effectively closed." Only 8 ships in 2 days vs
  100+/day pre-war. Iran charging $1M+ tolls. Iran blocks Chinese ships. 230
  loaded tankers trapped.** Brent $101.
- Apr 10: Iranian delegates arrive in Islamabad. White House warns staff over
  prediction market bets. Brent $97.
- **Apr 11: Islamabad talks begin. VP Vance + Witkoff + Kushner in 21+ hour
  marathon session. Trump says US forces "clearing" Hormuz.** Brent ~$98.
- **Apr 12 (today): TALKS FAIL. Vance: "Iranians have chosen not to accept our
  terms." Sticking points: Lebanon, sanctions, guarantees. Ceasefire continues
  through ~April 21 but no deal.** Brent ~$98, expected to gap up Monday.

### Current Market State (as of Apr 12, 2026)
- **Strait of Hormuz: effectively closed.** Iran charging tolls, limiting
  traffic to a trickle.
- **Ceasefire: fragile, 10 days remaining.** No formal agreement. Talks ongoing
  but stalled.

### Prediction Market Contracts
- **KXUSAIRANAGREEMENT**: "Will the US and Iran reach a formal agreement?" Resolves YES on a SIGNED DEAL (not just ceasefire). Historical precedent: JCPOA took 2+ years of formal negotiations.
- **KXCLOSEHORMUZ**: "Will Iran close Strait of Hormuz for 7+ days?" Already settled YES. Sub-contracts on reopening timing.
- **KXWTIMAX/KXWTIMIN**: Oil price range contracts. WTI max/min thresholds for year-end.
"""


def get_crisis_context() -> str:
    """Return the full crisis context for prompt injection."""
    return CRISIS_TIMELINE
