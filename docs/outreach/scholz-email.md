# Outreach — email to J. B. Scholz (peer-register version)

**Status: DRAFT, NOT SENT.** This file holds the final text only. Fill the two bracketed
placeholders, confirm a current address (see the note at the bottom), and send by hand.

---

**To:** Jason B. Scholz
**Subject:** An open replication of your 2011 BDM reconstruction — and a result I'd value your read on

Dear Dr Scholz,

I have built a complete, open, deterministic implementation of the Bueno de Mesquita expected-utility group-decision model, working directly from your reconstruction with Calbert and Smith (Scholz, Calbert & Smith, *Journal of Theoretical Politics*, 2011). Every equation is transcribed from the paper rather than from memory, and every interpretive choice where the reconstruction leaves latitude is logged against the equation and page it came from. The engine is fully reproducible: a fixed seed and fixed inputs give a byte-identical result, and the whole study regenerates from public artifacts with one command.

I am writing to register the work with you before I post the preprint, because you are the person best placed to tell me whether the reconstruction is faithful — and because the central result is a negative one, which I would rather have stress-tested by an expert than defended by an enthusiast.

The replication reproduces your reference case. But evaluated on the 351 expert-coded EU legislative controversies of the DEU III dataset, with sourced treaty-regime Council capabilities and reference points, the challenge (expected-utility) model does not beat a far simpler benchmark — the capability-and-salience-weighted mean of actor positions. A pre-registered successor search, its data split committed to version control before any model was written, failed to beat the mean; a flexible cross-validated oracle then placed the mean at the extractable-signal ceiling for this domain and input set. Since then I have widened the comparison to eight distinct solution concepts spanning the field's traditions — expected-utility bargaining and its quantal-response softening, the Nash and Kalai-Smorodinsky bargaining solutions, the probabilistic-Condorcet method KTAB implements, and two fitted structural blends. None separates from the weighted mean on held-out data. The closest, probabilistic Condorcet, posts a nominally lower error whose confidence interval still straddles zero.

My reading is that the lineage's documented successes — including the model outperforming the analysts who supplied its inputs — come from disciplined, structured elicitation rather than from the solution dynamics: structure, not magic. I am careful about the scope. The claim is conditional on the cooperative EU-legislative domain and the classic input set; the model's home-turf claim, superiority in coercive crises, I hold open, and I am assembling an ex-ante, blind-dual-entry coded case library and a cryptographically sealed forecast ledger to test it fairly rather than pronounce on it now.

Three things I would genuinely value from you, if you have the time: whether the reconstruction as I have implemented it is faithful to your intent; whether the ceiling reading is fair or overstated; and any pointer to expert-coded coercive tables I might use to give the mechanism its proper test. Everything — code, data provenance, and the manuscript — is open at the repository below, and I am happy to walk you through any part of it.

With thanks for the reconstruction that made this possible,

Hassan [surname]
Independent Researcher
https://github.com/hamzagul07/schelling

---

**Where to find Jason Scholz:** the 2011 paper lists the Defence Science and Technology Organisation
(DSTO, now DSTG), Australia; he subsequently led the Trusted Autonomous Systems Defence CRC (Australia)
as CEO/Chief Scientist — a current email is best confirmed via those institutions, his recent
publications, or a professional profile before sending. Do not send to an unverified address.
