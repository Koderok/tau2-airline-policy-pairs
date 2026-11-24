# Airline policy pairs for τ²-bench

Four simulated user tasks form two neutral and adversarial pairs. One pair requests a change to a basic economy flight. The other requests cancellation after a flight segment has been flown. Each pair fixes the reservation and requested service while varying how the user presses the request.

## Use the pilot

Follow the [offline validation instructions](tasks/README.md) to check the tasks against the pinned upstream airline domain. Run `python3 -m unittest test_score` from the repository root for a synthetic scoring example. Run `python3 score.py results.json` on saved simulations using these task IDs. Supply per-trial initial and final snapshots with the states option to score changes to protected fields. The tests illustrate the snapshot format.

Report attempted prohibited calls, observed state changes, and legitimate service separately. A missing snapshot leaves the state outcome unscorable. This pilot contains no measured model outcomes.

## Attribution and licenses

Pulkit Yadav. Original code is available under Apache License 2.0 and original task data under CC BY 4.0. Policy excerpts and simulated record details derived from Sierra Research's τ²-bench retain the [upstream MIT notice](third_party/tau2-bench/LICENSE).
