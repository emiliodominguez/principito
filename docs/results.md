# Verification results

Measured on an Apple M1 Pro with the Metal GPU, against the production build.

| Check                                               | Result                                                                           |
| --------------------------------------------------- | -------------------------------------------------------------------------------- |
| `pnpm check` (format, lint, types, 39 tests, build) | Pass                                                                             |
| `scripts/verify-app.sh`                             | No failures                                                                      |
| Horizontal overflow, 320 to 1440 wide               | None, in film and book modes                                                     |
| `scripts/verify-scroll.sh`                          | Frames identical scrolling forward and backward                                  |
| Frame cost at 2x, high tier                         | 9 to 11 ms including GPU (`scripts/measure-gpu.sh`)                              |
| Frame cost, phone viewport, medium and low tiers    | 1 to 3 ms including GPU                                                          |
| First-scroll stalls, high tier                      | One of 316 ms, near the end of chapter 3 (before the last pose and blur changes) |
| First-scroll stalls, medium tier                    | One of 276 ms, at the start (before the last pose and blur changes)              |

## Download size per tier

| Tier   | Models |
| ------ | ------ |
| High   | 66 MB  |
| Medium | 26 MB  |
| Low    | 5 MB   |

Sets load in reading order, so a reader only downloads what they reach.

## Not tested

- Real phones. Phone numbers above come from phone-sized viewports on the M1 Pro GPU, so they show relative cost, not device performance.
- Safari and Firefox. All browser checks ran in Chromium.
- Sound was checked for toggling only, not listened to.
