# Per-revision audit table

Use this table to manually spot-check the wait-time numbers against the live Phab revision page (`https://phabricator.services.mozilla.com/D<n>`).

- Generated: 2026-05-16T22:45:00.629018+00:00
- Revisions in raw_data/: **521**
- Have a `created` timestamp: **293**
- Have a first reaction (comment/accept/request-changes/reject) by a listed member: **262**
- Have an explicit `accept` by a listed member: **260**
- Have a computable **queue wait** (group added then member reacted): **166**

Member set (from `reviewstats/members.py`): alwu, aosmond, azebrowski, chunmin, jolin, karlt, kinetik, padenot

Bots filtered out: `phab-bot`, `Lando`, `lando-bot`, `Herald`. The author of the revision is also skipped (self-reaction doesn't count).

---

| # | Revision | Author | Created | Group added | First reaction | Time to react | First accept | Time to accept |
|--:|---|---|---|---|---|--:|---|--:|
| 1 | [D155376](https://phabricator.services.mozilla.com/D155376) | — | — | — | — | — | — | — |
| 2 | [D263249](https://phabricator.services.mozilla.com/D263249) | — | — | — | — | — | — | — |
| 3 | [D263717](https://phabricator.services.mozilla.com/D263717) | — | — | — | 2025-12-01 12:36:31 UTC by **padenot** (accept) | — | 2025-12-01 12:36:31 UTC by **padenot** | — |
| 4 | [D263719](https://phabricator.services.mozilla.com/D263719) | — | — | — | 2025-09-04 13:43:51 UTC by **azebrowski** (comment) | — | 2025-12-01 12:36:10 UTC by **padenot** | — |
| 5 | [D263720](https://phabricator.services.mozilla.com/D263720) | — | — | 2025-10-13 16:50:36 UTC | 2025-12-01 12:36:14 UTC by **padenot** (accept) | 48.82 d | 2025-12-01 12:36:14 UTC by **padenot** | 48.82 d |
| 6 | [D265268](https://phabricator.services.mozilla.com/D265268) | vhilla | 2025-09-18 12:42:53 UTC | — | — | — | — | — |
| 7 | [D265560](https://phabricator.services.mozilla.com/D265560) | karlt | 2025-09-21 21:42:02 UTC | — | — | — | — | — |
| 8 | [D268499](https://phabricator.services.mozilla.com/D268499) | — | — | — | 2025-11-19 21:38:04 UTC by **alwu** (comment) | — | 2025-12-29 19:36:02 UTC by **alwu** | — |
| 9 | [D268717](https://phabricator.services.mozilla.com/D268717) | nika | 2025-10-15 15:01:30 UTC | 2025-10-15 15:02:11 UTC | 2025-10-15 22:52:23 UTC by **karlt** (accept) | 7.8 h | 2025-10-15 22:52:23 UTC by **karlt** | 7.8 h |
| 10 | [D269914](https://phabricator.services.mozilla.com/D269914) | — | — | — | 2025-11-24 02:56:12 UTC by **karlt** (request-changes) | — | 2025-12-10 03:50:35 UTC by **karlt** | — |
| 11 | [D271044](https://phabricator.services.mozilla.com/D271044) | — | — | — | — | — | — | — |
| 12 | [D271045](https://phabricator.services.mozilla.com/D271045) | — | — | — | — | — | — | — |
| 13 | [D271046](https://phabricator.services.mozilla.com/D271046) | — | — | — | — | — | — | — |
| 14 | [D271204](https://phabricator.services.mozilla.com/D271204) | — | — | — | — | — | — | — |
| 15 | [D271415](https://phabricator.services.mozilla.com/D271415) | azebrowski | 2025-11-05 16:09:56 UTC | — | 2025-11-06 18:28:48 UTC by **aosmond** (accept) | — | 2025-11-06 18:28:48 UTC by **aosmond** | — |
| 16 | [D272096](https://phabricator.services.mozilla.com/D272096) | — | — | — | — | — | — | — |
| 17 | [D272112](https://phabricator.services.mozilla.com/D272112) | padenot | 2025-11-11 03:32:48 UTC | — | 2025-11-11 05:59:41 UTC by **karlt** (accept) | — | 2025-11-11 05:59:41 UTC by **karlt** | — |
| 18 | [D272113](https://phabricator.services.mozilla.com/D272113) | padenot | 2025-11-11 03:32:48 UTC | 2025-11-11 03:35:47 UTC | 2025-11-11 20:47:59 UTC by **karlt** (comment) | 17.2 h | 2025-11-24 21:35:46 UTC by **karlt** | 13.75 d |
| 19 | [D272174](https://phabricator.services.mozilla.com/D272174) | Standard8 | 2025-11-11 20:27:34 UTC | — | — | — | — | — |
| 20 | [D272241](https://phabricator.services.mozilla.com/D272241) | pehrsons | 2025-11-12 14:05:37 UTC | — | — | — | — | — |
| 21 | [D272252](https://phabricator.services.mozilla.com/D272252) | gaston | 2025-11-12 15:07:08 UTC | — | 2025-11-17 21:58:26 UTC by **alwu** (accept) | — | 2025-11-17 21:58:26 UTC by **alwu** | — |
| 22 | [D272253](https://phabricator.services.mozilla.com/D272253) | gaston | 2025-11-12 15:07:13 UTC | — | 2025-11-17 21:53:27 UTC by **alwu** (accept) | — | 2025-11-17 21:53:27 UTC by **alwu** | — |
| 23 | [D272254](https://phabricator.services.mozilla.com/D272254) | gaston | 2025-11-12 15:07:18 UTC | — | 2025-11-17 22:03:06 UTC by **alwu** (accept) | — | 2025-11-17 22:03:06 UTC by **alwu** | — |
| 24 | [D272255](https://phabricator.services.mozilla.com/D272255) | gaston | 2025-11-12 15:07:23 UTC | — | 2025-11-17 22:04:11 UTC by **alwu** (accept) | — | 2025-11-17 22:04:11 UTC by **alwu** | — |
| 25 | [D272256](https://phabricator.services.mozilla.com/D272256) | gaston | 2025-11-12 15:07:28 UTC | — | 2025-11-17 21:58:26 UTC by **alwu** (comment) | — | 2025-11-24 15:37:25 UTC by **padenot** | — |
| 26 | [D272371](https://phabricator.services.mozilla.com/D272371) | — | — | — | — | — | — | — |
| 27 | [D272471](https://phabricator.services.mozilla.com/D272471) | longsonr | 2025-11-13 15:49:24 UTC | 2025-11-13 15:51:01 UTC | 2025-11-13 22:11:18 UTC by **karlt** (accept) | 6.3 h | 2025-11-13 22:11:18 UTC by **karlt** | 6.3 h |
| 28 | [D272530](https://phabricator.services.mozilla.com/D272530) | — | — | — | 2025-11-21 22:00:26 UTC by **karlt** (accept) | — | 2025-11-21 22:00:26 UTC by **karlt** | — |
| 29 | [D272604](https://phabricator.services.mozilla.com/D272604) | karlt | 2025-11-14 07:50:21 UTC | — | — | — | — | — |
| 30 | [D272605](https://phabricator.services.mozilla.com/D272605) | karlt | 2025-11-14 07:50:28 UTC | — | — | — | — | — |
| 31 | [D272606](https://phabricator.services.mozilla.com/D272606) | karlt | 2025-11-14 07:50:34 UTC | — | — | — | — | — |
| 32 | [D272607](https://phabricator.services.mozilla.com/D272607) | karlt | 2025-11-14 07:50:41 UTC | — | — | — | — | — |
| 33 | [D272613](https://phabricator.services.mozilla.com/D272613) | pehrsons | 2025-11-14 09:26:26 UTC | 2025-11-14 09:26:36 UTC | 2025-11-21 13:08:31 UTC by **aosmond** (accept) | 7.15 d | 2025-11-21 13:08:31 UTC by **aosmond** | 7.15 d |
| 34 | [D272640](https://phabricator.services.mozilla.com/D272640) | — | — | 2025-11-14 13:54:20 UTC | 2025-11-17 06:53:22 UTC by **karlt** (request-changes) | 2.71 d | 2025-11-20 22:52:01 UTC by **karlt** | 6.37 d |
| 35 | [D272815](https://phabricator.services.mozilla.com/D272815) | — | — | — | 2025-11-17 21:42:19 UTC by **alwu** (accept) | — | 2025-11-17 21:42:19 UTC by **alwu** | — |
| 36 | [D273013](https://phabricator.services.mozilla.com/D273013) | gregp | 2025-11-18 13:57:56 UTC | 2025-11-18 13:59:41 UTC | 2025-11-18 16:21:56 UTC by **aosmond** (accept) | 2.4 h | 2025-11-18 16:21:56 UTC by **aosmond** | 2.4 h |
| 37 | [D273098](https://phabricator.services.mozilla.com/D273098) | AlaskanEmily | 2025-11-18 20:35:43 UTC | 2025-11-18 20:35:53 UTC | 2025-11-19 21:39:04 UTC by **alwu** (accept) | 1.04 d | 2025-11-19 21:39:04 UTC by **alwu** | 1.04 d |
| 38 | [D273320](https://phabricator.services.mozilla.com/D273320) | — | — | — | 2026-01-16 03:46:30 UTC by **karlt** (accept) | — | 2026-01-16 03:46:30 UTC by **karlt** | — |
| 39 | [D273703](https://phabricator.services.mozilla.com/D273703) | aosmond | 2025-11-22 03:24:52 UTC | 2025-11-22 03:24:57 UTC | 2025-11-23 20:18:41 UTC by **karlt** (accept) | 1.70 d | 2025-11-23 20:18:41 UTC by **karlt** | 1.70 d |
| 40 | [D273704](https://phabricator.services.mozilla.com/D273704) | aosmond | 2025-11-22 03:29:09 UTC | 2025-11-22 03:29:18 UTC | 2025-12-01 13:40:52 UTC by **padenot** (accept) | 9.42 d | 2025-12-01 13:40:52 UTC by **padenot** | 9.42 d |
| 41 | [D273705](https://phabricator.services.mozilla.com/D273705) | aosmond | 2025-11-22 03:32:40 UTC | 2025-11-22 03:47:45 UTC | 2025-11-24 22:11:47 UTC by **azebrowski** (accept) | 2.77 d | 2025-11-24 22:11:47 UTC by **azebrowski** | 2.77 d |
| 42 | [D273706](https://phabricator.services.mozilla.com/D273706) | aosmond | 2025-11-22 03:35:23 UTC | 2025-11-22 03:35:30 UTC | 2025-12-01 13:41:31 UTC by **padenot** (accept) | 9.42 d | 2025-12-01 13:41:31 UTC by **padenot** | 9.42 d |
| 43 | [D273708](https://phabricator.services.mozilla.com/D273708) | aosmond | 2025-11-22 03:46:08 UTC | 2025-11-22 03:46:22 UTC | 2025-11-24 18:37:58 UTC by **azebrowski** (accept) | 2.62 d | 2025-11-24 18:37:58 UTC by **azebrowski** | 2.62 d |
| 44 | [D273763](https://phabricator.services.mozilla.com/D273763) | azebrowski | 2025-11-24 06:19:41 UTC | — | — | — | — | — |
| 45 | [D273764](https://phabricator.services.mozilla.com/D273764) | azebrowski | 2025-11-24 06:19:44 UTC | — | — | — | — | — |
| 46 | [D273781](https://phabricator.services.mozilla.com/D273781) | vhilla | 2025-11-24 09:56:56 UTC | — | — | — | — | — |
| 47 | [D273802](https://phabricator.services.mozilla.com/D273802) | — | — | — | 2025-12-01 02:02:43 UTC by **aosmond** (accept) | — | 2025-12-01 02:02:43 UTC by **aosmond** | — |
| 48 | [D273846](https://phabricator.services.mozilla.com/D273846) | ArnaudBienner | 2025-11-24 15:35:24 UTC | 2025-11-24 15:36:19 UTC | 2025-11-24 22:09:17 UTC by **karlt** (accept) | 6.5 h | 2025-11-24 22:09:17 UTC by **karlt** | 6.5 h |
| 49 | [D273930](https://phabricator.services.mozilla.com/D273930) | — | — | 2025-12-01 22:34:52 UTC | 2025-12-01 23:56:59 UTC by **alwu** (accept) | 1.4 h | 2025-12-01 23:56:59 UTC by **alwu** | 1.4 h |
| 50 | [D273931](https://phabricator.services.mozilla.com/D273931) | — | — | 2025-12-01 22:35:03 UTC | 2025-12-01 23:56:38 UTC by **alwu** (accept) | 1.4 h | 2025-12-01 23:56:38 UTC by **alwu** | 1.4 h |
| 51 | [D274164](https://phabricator.services.mozilla.com/D274164) | jolin | 2025-11-26 19:17:05 UTC | — | 2025-12-01 02:02:06 UTC by **aosmond** (accept) | — | 2025-12-01 02:02:06 UTC by **aosmond** | — |
| 52 | [D274242](https://phabricator.services.mozilla.com/D274242) | aosmond | 2025-11-27 05:00:57 UTC | 2025-11-27 05:01:04 UTC | 2025-11-27 08:48:52 UTC by **padenot** (accept) | 3.8 h | 2025-11-27 08:48:52 UTC by **padenot** | 3.8 h |
| 53 | [D274245](https://phabricator.services.mozilla.com/D274245) | karlt | 2025-11-27 07:41:18 UTC | — | — | — | — | — |
| 54 | [D274437](https://phabricator.services.mozilla.com/D274437) | — | — | — | — | — | — | — |
| 55 | [D274501](https://phabricator.services.mozilla.com/D274501) | cpeterson | 2025-11-30 05:06:36 UTC | — | 2025-12-01 02:03:15 UTC by **aosmond** (accept) | — | 2025-12-01 02:03:15 UTC by **aosmond** | — |
| 56 | [D274517](https://phabricator.services.mozilla.com/D274517) | sfarre | 2025-11-30 12:22:01 UTC | 2026-01-08 16:20:07 UTC | 2026-01-14 18:34:24 UTC by **alwu** (accept) | 6.09 d | 2026-01-14 18:34:24 UTC by **alwu** | 6.09 d |
| 57 | [D274571](https://phabricator.services.mozilla.com/D274571) | — | — | 2025-12-01 14:44:54 UTC | 2025-12-01 19:31:48 UTC by **alwu** (accept) | 4.8 h | 2025-12-01 19:31:48 UTC by **alwu** | 4.8 h |
| 58 | [D274690](https://phabricator.services.mozilla.com/D274690) | ahochheiden | 2025-12-02 04:41:44 UTC | 2025-12-02 04:44:34 UTC | 2025-12-02 12:50:03 UTC by **padenot** (accept) | 8.1 h | 2025-12-02 12:50:03 UTC by **padenot** | 8.1 h |
| 59 | [D274699](https://phabricator.services.mozilla.com/D274699) | ahochheiden | 2025-12-02 04:42:31 UTC | — | 2025-12-02 12:50:15 UTC by **padenot** (accept) | — | 2025-12-02 12:50:15 UTC by **padenot** | — |
| 60 | [D274710](https://phabricator.services.mozilla.com/D274710) | m_kato | 2025-12-02 06:04:16 UTC | — | 2025-12-02 18:40:23 UTC by **jolin** (accept) | — | 2025-12-02 18:40:23 UTC by **jolin** | — |
| 61 | [D274755](https://phabricator.services.mozilla.com/D274755) | pehrsons | 2025-12-02 14:42:44 UTC | — | 2025-12-05 14:37:51 UTC by **padenot** (accept) | — | 2025-12-05 14:37:51 UTC by **padenot** | — |
| 62 | [D275011](https://phabricator.services.mozilla.com/D275011) | aosmond | 2025-12-03 23:18:30 UTC | 2025-12-03 23:18:37 UTC | 2025-12-04 00:09:55 UTC by **jolin** (accept) | 0.9 h | 2025-12-04 00:09:55 UTC by **jolin** | 0.9 h |
| 63 | [D275103](https://phabricator.services.mozilla.com/D275103) | aosmond | 2025-12-04 19:28:27 UTC | 2025-12-04 19:29:51 UTC | 2025-12-04 19:38:35 UTC by **jolin** (accept) | 0.1 h | 2025-12-04 19:38:35 UTC by **jolin** | 0.1 h |
| 64 | [D275105](https://phabricator.services.mozilla.com/D275105) | aosmond | 2025-12-04 19:30:43 UTC | 2025-12-04 19:30:53 UTC | 2025-12-04 19:46:54 UTC by **jolin** (accept) | 0.3 h | 2025-12-04 19:46:54 UTC by **jolin** | 0.3 h |
| 65 | [D275132](https://phabricator.services.mozilla.com/D275132) | AlaskanEmily | 2025-12-04 22:25:39 UTC | — | — | — | — | — |
| 66 | [D275151](https://phabricator.services.mozilla.com/D275151) | ahochheiden | 2025-12-05 01:53:17 UTC | 2025-12-05 01:53:22 UTC | 2025-12-05 19:33:34 UTC by **alwu** (accept) | 17.7 h | 2025-12-05 19:33:34 UTC by **alwu** | 17.7 h |
| 67 | [D275539](https://phabricator.services.mozilla.com/D275539) | ArnaudBienner | 2025-12-08 23:29:03 UTC | 2025-12-08 23:29:10 UTC | 2025-12-09 00:07:47 UTC by **karlt** (accept) | 0.6 h | 2025-12-09 00:07:47 UTC by **karlt** | 0.6 h |
| 68 | [D275550](https://phabricator.services.mozilla.com/D275550) | karlt | 2025-12-09 03:35:27 UTC | 2025-12-09 03:35:32 UTC | 2025-12-10 18:45:16 UTC by **chunmin** (accept) | 1.63 d | 2025-12-10 18:45:16 UTC by **chunmin** | 1.63 d |
| 69 | [D275551](https://phabricator.services.mozilla.com/D275551) | karlt | 2025-12-09 03:35:32 UTC | 2025-12-09 03:35:43 UTC | 2025-12-09 16:31:00 UTC by **padenot** (accept) | 12.9 h | 2025-12-09 16:31:00 UTC by **padenot** | 12.9 h |
| 70 | [D275616](https://phabricator.services.mozilla.com/D275616) | sergesanspaille | 2025-12-09 13:20:47 UTC | 2025-12-09 13:20:53 UTC | 2025-12-09 14:17:27 UTC by **padenot** (accept) | 0.9 h | 2025-12-09 14:17:27 UTC by **padenot** | 0.9 h |
| 71 | [D275692](https://phabricator.services.mozilla.com/D275692) | chunmin | 2025-12-09 22:58:01 UTC | — | — | — | — | — |
| 72 | [D275700](https://phabricator.services.mozilla.com/D275700) | aosmond | 2025-12-10 00:02:46 UTC | 2025-12-10 00:02:55 UTC | 2025-12-10 04:54:24 UTC by **karlt** (accept) | 4.9 h | 2025-12-10 04:54:24 UTC by **karlt** | 4.9 h |
| 73 | [D275701](https://phabricator.services.mozilla.com/D275701) | aosmond | 2025-12-10 00:03:29 UTC | 2025-12-10 00:03:38 UTC | 2025-12-10 16:10:23 UTC by **padenot** (accept) | 16.1 h | 2025-12-10 16:10:23 UTC by **padenot** | 16.1 h |
| 74 | [D275718](https://phabricator.services.mozilla.com/D275718) | aosmond | 2025-12-10 03:17:59 UTC | 2025-12-10 03:19:09 UTC | 2025-12-10 16:16:51 UTC by **padenot** (accept) | 13.0 h | 2025-12-10 16:16:51 UTC by **padenot** | 13.0 h |
| 75 | [D275720](https://phabricator.services.mozilla.com/D275720) | aosmond | 2025-12-10 03:41:55 UTC | 2025-12-10 03:42:07 UTC | 2025-12-10 16:30:49 UTC by **padenot** (accept) | 12.8 h | 2025-12-10 16:30:49 UTC by **padenot** | 12.8 h |
| 76 | [D275722](https://phabricator.services.mozilla.com/D275722) | aosmond | 2025-12-10 03:42:04 UTC | 2025-12-10 03:42:21 UTC | 2025-12-10 16:36:37 UTC by **padenot** (accept) | 12.9 h | 2025-12-10 16:36:37 UTC by **padenot** | 12.9 h |
| 77 | [D275723](https://phabricator.services.mozilla.com/D275723) | aosmond | 2025-12-10 03:42:08 UTC | 2025-12-10 03:42:26 UTC | 2025-12-10 16:37:16 UTC by **padenot** (accept) | 12.9 h | 2025-12-10 16:37:16 UTC by **padenot** | 12.9 h |
| 78 | [D275724](https://phabricator.services.mozilla.com/D275724) | aosmond | 2025-12-10 03:42:13 UTC | 2025-12-10 03:42:31 UTC | 2025-12-10 16:37:30 UTC by **padenot** (accept) | 12.9 h | 2025-12-10 16:37:30 UTC by **padenot** | 12.9 h |
| 79 | [D275725](https://phabricator.services.mozilla.com/D275725) | aosmond | 2025-12-10 03:42:18 UTC | 2025-12-10 03:42:41 UTC | 2025-12-10 16:39:35 UTC by **padenot** (accept) | 12.9 h | 2025-12-10 16:39:35 UTC by **padenot** | 12.9 h |
| 80 | [D275740](https://phabricator.services.mozilla.com/D275740) | karlt | 2025-12-10 07:37:40 UTC | 2025-12-10 07:39:00 UTC | 2025-12-10 18:45:38 UTC by **chunmin** (accept) | 11.1 h | 2025-12-10 18:45:38 UTC by **chunmin** | 11.1 h |
| 81 | [D275757](https://phabricator.services.mozilla.com/D275757) | Standard8 | 2025-12-10 11:51:36 UTC | 2025-12-10 11:51:58 UTC | 2025-12-15 19:00:44 UTC by **alwu** (accept) | 5.30 d | 2025-12-15 19:00:44 UTC by **alwu** | 5.30 d |
| 82 | [D275781](https://phabricator.services.mozilla.com/D275781) | padenot | 2025-12-10 14:07:46 UTC | 2025-12-10 14:07:52 UTC | 2025-12-10 23:51:06 UTC by **karlt** (accept) | 9.7 h | 2025-12-10 23:51:06 UTC by **karlt** | 9.7 h |
| 83 | [D276059](https://phabricator.services.mozilla.com/D276059) | nika | 2025-12-11 19:10:25 UTC | — | 2026-03-09 18:51:34 UTC by **padenot** (accept) | — | 2026-03-09 18:51:34 UTC by **padenot** | — |
| 84 | [D276307](https://phabricator.services.mozilla.com/D276307) | chunmin | 2025-12-12 21:59:27 UTC | 2025-12-12 21:59:33 UTC | 2025-12-15 16:21:19 UTC by **padenot** (accept) | 2.77 d | 2025-12-15 16:21:19 UTC by **padenot** | 2.77 d |
| 85 | [D276410](https://phabricator.services.mozilla.com/D276410) | karlt | 2025-12-15 07:15:51 UTC | — | — | — | — | — |
| 86 | [D276411](https://phabricator.services.mozilla.com/D276411) | karlt | 2025-12-15 07:15:58 UTC | — | — | — | — | — |
| 87 | [D276412](https://phabricator.services.mozilla.com/D276412) | karlt | 2025-12-15 07:16:06 UTC | — | 2025-12-16 18:13:12 UTC by **padenot** (accept) | — | 2025-12-16 18:13:12 UTC by **padenot** | — |
| 88 | [D276499](https://phabricator.services.mozilla.com/D276499) | jolin | 2025-12-15 17:36:49 UTC | 2025-12-15 17:36:54 UTC | 2025-12-15 20:10:47 UTC by **alwu** (accept) | 2.6 h | 2025-12-15 20:10:47 UTC by **alwu** | 2.6 h |
| 89 | [D276894](https://phabricator.services.mozilla.com/D276894) | — | — | — | 2025-12-18 10:58:21 UTC by **padenot** (accept) | — | 2025-12-18 10:58:21 UTC by **padenot** | — |
| 90 | [D276985](https://phabricator.services.mozilla.com/D276985) | padenot | 2025-12-18 10:42:45 UTC | — | 2025-12-18 21:54:13 UTC by **chunmin** (accept) | — | 2025-12-18 21:54:13 UTC by **chunmin** | — |
| 91 | [D277268](https://phabricator.services.mozilla.com/D277268) | RyanVM | 2025-12-20 00:05:52 UTC | 2025-12-20 00:06:00 UTC | 2025-12-22 05:05:37 UTC by **karlt** (accept) | 2.21 d | 2025-12-22 05:05:37 UTC by **karlt** | 2.21 d |
| 92 | [D277315](https://phabricator.services.mozilla.com/D277315) | sergesanspaille | 2025-12-22 10:57:05 UTC | — | 2025-12-23 21:28:36 UTC by **aosmond** (accept) | — | 2025-12-23 21:28:36 UTC by **aosmond** | — |
| 93 | [D277317](https://phabricator.services.mozilla.com/D277317) | sergesanspaille | 2025-12-22 10:57:12 UTC | — | — | — | — | — |
| 94 | [D277625](https://phabricator.services.mozilla.com/D277625) | — | — | 2026-01-06 20:43:20 UTC | 2026-01-09 16:02:03 UTC by **padenot** (accept) | 2.80 d | 2026-01-09 16:02:03 UTC by **padenot** | 2.80 d |
| 95 | [D277626](https://phabricator.services.mozilla.com/D277626) | — | — | 2026-01-06 20:43:25 UTC | 2026-01-07 02:40:02 UTC by **alwu** (comment) | 5.9 h | 2026-01-14 15:39:13 UTC by **padenot** | 7.79 d |
| 96 | [D277683](https://phabricator.services.mozilla.com/D277683) | karlt | 2025-12-31 07:44:20 UTC | — | 2026-01-02 02:15:07 UTC by **aosmond** (accept) | — | 2026-01-02 02:15:07 UTC by **aosmond** | — |
| 97 | [D277703](https://phabricator.services.mozilla.com/D277703) | aosmond | 2025-12-31 16:04:42 UTC | 2025-12-31 16:07:18 UTC | 2025-12-31 19:06:56 UTC by **jolin** (accept) | 3.0 h | 2025-12-31 19:06:56 UTC by **jolin** | 3.0 h |
| 98 | [D277717](https://phabricator.services.mozilla.com/D277717) | aosmond | 2025-12-31 21:22:54 UTC | 2025-12-31 21:24:19 UTC | 2025-12-31 22:19:51 UTC by **jolin** (accept) | 0.9 h | 2025-12-31 22:19:51 UTC by **jolin** | 0.9 h |
| 99 | [D277720](https://phabricator.services.mozilla.com/D277720) | — | — | 2026-01-06 20:43:28 UTC | 2026-01-10 02:32:04 UTC by **alwu** (comment) | 3.24 d | 2026-01-15 14:28:36 UTC by **padenot** | 8.74 d |
| 100 | [D277730](https://phabricator.services.mozilla.com/D277730) | karlt | 2026-01-01 08:03:30 UTC | — | — | — | — | — |
| 101 | [D277745](https://phabricator.services.mozilla.com/D277745) | aosmond | 2026-01-02 03:51:45 UTC | 2026-01-02 03:52:00 UTC | 2026-01-05 00:13:21 UTC by **karlt** (accept) | 2.85 d | 2026-01-05 00:13:21 UTC by **karlt** | 2.85 d |
| 102 | [D277756](https://phabricator.services.mozilla.com/D277756) | myfreeweb | 2026-01-02 13:49:51 UTC | — | 2026-01-05 15:15:56 UTC by **aosmond** (accept) | — | 2026-01-05 15:15:56 UTC by **aosmond** | — |
| 103 | [D277786](https://phabricator.services.mozilla.com/D277786) | — | — | 2026-01-06 20:43:31 UTC | 2026-01-09 16:37:09 UTC by **padenot** (accept) | 2.83 d | 2026-01-09 16:37:09 UTC by **padenot** | 2.83 d |
| 104 | [D277796](https://phabricator.services.mozilla.com/D277796) | aosmond | 2026-01-03 15:54:27 UTC | 2026-01-03 15:57:18 UTC | 2026-01-05 16:19:48 UTC by **jolin** (request-changes) | 2.02 d | 2026-01-05 17:16:28 UTC by **padenot** | 2.05 d |
| 105 | [D277797](https://phabricator.services.mozilla.com/D277797) | aosmond | 2026-01-03 15:54:31 UTC | 2026-01-03 15:57:24 UTC | 2026-01-05 16:47:42 UTC by **jolin** (accept) | 2.03 d | 2026-01-05 16:47:42 UTC by **jolin** | 2.03 d |
| 106 | [D277798](https://phabricator.services.mozilla.com/D277798) | aosmond | 2026-01-03 15:54:35 UTC | 2026-01-03 15:57:28 UTC | 2026-01-05 17:08:02 UTC by **jolin** (accept) | 2.05 d | 2026-01-05 17:08:02 UTC by **jolin** | 2.05 d |
| 107 | [D277799](https://phabricator.services.mozilla.com/D277799) | aosmond | 2026-01-03 15:54:39 UTC | 2026-01-03 15:57:32 UTC | 2026-01-05 17:14:51 UTC by **jolin** (accept) | 2.05 d | 2026-01-05 17:14:51 UTC by **jolin** | 2.05 d |
| 108 | [D277800](https://phabricator.services.mozilla.com/D277800) | aosmond | 2026-01-03 15:54:43 UTC | 2026-01-03 15:57:38 UTC | 2026-01-05 17:17:07 UTC by **padenot** (accept) | 2.06 d | 2026-01-05 17:17:07 UTC by **padenot** | 2.06 d |
| 109 | [D277801](https://phabricator.services.mozilla.com/D277801) | aosmond | 2026-01-03 15:55:21 UTC | 2026-01-03 15:57:42 UTC | 2026-01-05 20:20:24 UTC by **jolin** (accept) | 2.18 d | 2026-01-05 20:20:24 UTC by **jolin** | 2.18 d |
| 110 | [D277812](https://phabricator.services.mozilla.com/D277812) | aosmond | 2026-01-04 12:56:38 UTC | 2026-01-04 12:56:48 UTC | 2026-01-05 00:22:46 UTC by **karlt** (accept) | 11.4 h | 2026-01-05 00:22:46 UTC by **karlt** | 11.4 h |
| 111 | [D277814](https://phabricator.services.mozilla.com/D277814) | aosmond | 2026-01-04 18:18:14 UTC | 2026-01-04 18:18:24 UTC | 2026-01-05 20:22:07 UTC by **jolin** (accept) | 1.09 d | 2026-01-05 20:22:07 UTC by **jolin** | 1.09 d |
| 112 | [D277835](https://phabricator.services.mozilla.com/D277835) | karlt | 2026-01-05 09:34:27 UTC | — | — | — | — | — |
| 113 | [D277975](https://phabricator.services.mozilla.com/D277975) | sergesanspaille | 2026-01-06 09:07:03 UTC | — | — | — | — | — |
| 114 | [D277976](https://phabricator.services.mozilla.com/D277976) | sergesanspaille | 2026-01-06 09:07:13 UTC | 2026-01-06 09:10:58 UTC | 2026-01-06 11:00:04 UTC by **padenot** (accept) | 1.8 h | 2026-01-06 11:00:04 UTC by **padenot** | 1.8 h |
| 115 | [D277977](https://phabricator.services.mozilla.com/D277977) | sergesanspaille | 2026-01-06 09:07:20 UTC | — | 2026-01-06 11:01:38 UTC by **padenot** (accept) | — | 2026-01-06 11:01:38 UTC by **padenot** | — |
| 116 | [D277978](https://phabricator.services.mozilla.com/D277978) | sergesanspaille | 2026-01-06 09:07:28 UTC | — | — | — | — | — |
| 117 | [D277979](https://phabricator.services.mozilla.com/D277979) | sergesanspaille | 2026-01-06 09:07:38 UTC | — | 2026-01-06 11:02:09 UTC by **padenot** (accept) | — | 2026-01-06 11:02:09 UTC by **padenot** | — |
| 118 | [D277993](https://phabricator.services.mozilla.com/D277993) | padenot | 2026-01-06 13:00:26 UTC | — | 2026-01-07 06:17:35 UTC by **karlt** (accept) | — | 2026-01-07 06:17:35 UTC by **karlt** | — |
| 119 | [D278032](https://phabricator.services.mozilla.com/D278032) | — | — | 2026-01-06 20:43:50 UTC | 2026-01-06 20:51:29 UTC by **alwu** (comment) | 0.1 h | 2026-01-09 16:38:31 UTC by **padenot** | 2.83 d |
| 120 | [D278077](https://phabricator.services.mozilla.com/D278077) | aosmond | 2026-01-07 03:42:45 UTC | 2026-01-07 03:42:55 UTC | 2026-01-07 13:57:27 UTC by **padenot** (accept) | 10.2 h | 2026-01-07 13:57:27 UTC by **padenot** | 10.2 h |
| 121 | [D278210](https://phabricator.services.mozilla.com/D278210) | alwu | 2026-01-07 23:33:54 UTC | 2026-01-07 23:36:33 UTC | 2026-01-09 16:23:54 UTC by **padenot** (accept) | 1.70 d | 2026-01-09 16:23:54 UTC by **padenot** | 1.70 d |
| 122 | [D278211](https://phabricator.services.mozilla.com/D278211) | alwu | 2026-01-07 23:34:01 UTC | 2026-01-07 23:36:38 UTC | 2026-01-09 16:24:52 UTC by **padenot** (accept) | 1.70 d | 2026-01-09 16:24:52 UTC by **padenot** | 1.70 d |
| 123 | [D278212](https://phabricator.services.mozilla.com/D278212) | alwu | 2026-01-07 23:34:09 UTC | 2026-01-07 23:36:44 UTC | 2026-01-09 16:30:27 UTC by **padenot** (accept) | 1.70 d | 2026-01-09 16:30:27 UTC by **padenot** | 1.70 d |
| 124 | [D278230](https://phabricator.services.mozilla.com/D278230) | aosmond | 2026-01-08 03:44:41 UTC | 2026-01-08 03:45:42 UTC | 2026-01-08 15:36:26 UTC by **padenot** (accept) | 11.8 h | 2026-01-08 15:36:26 UTC by **padenot** | 11.8 h |
| 125 | [D278252](https://phabricator.services.mozilla.com/D278252) | sergesanspaille | 2026-01-08 09:24:32 UTC | — | — | — | — | — |
| 126 | [D278336](https://phabricator.services.mozilla.com/D278336) | aosmond | 2026-01-08 17:22:12 UTC | 2026-01-08 17:22:58 UTC | 2026-01-08 17:40:49 UTC by **alwu** (accept) | 0.3 h | 2026-01-08 17:40:49 UTC by **alwu** | 0.3 h |
| 127 | [D278365](https://phabricator.services.mozilla.com/D278365) | alwu | 2026-01-08 22:13:57 UTC | 2026-01-08 22:16:43 UTC | 2026-01-12 17:04:21 UTC by **padenot** (accept) | 3.78 d | 2026-01-12 17:04:21 UTC by **padenot** | 3.78 d |
| 128 | [D278425](https://phabricator.services.mozilla.com/D278425) | sergesanspaille | 2026-01-09 09:48:39 UTC | 2026-01-09 09:49:00 UTC | 2026-01-09 12:16:22 UTC by **padenot** (accept) | 2.5 h | 2026-01-09 12:16:22 UTC by **padenot** | 2.5 h |
| 129 | [D278540](https://phabricator.services.mozilla.com/D278540) | azebrowski | 2026-01-09 20:39:21 UTC | — | 2026-01-10 00:04:51 UTC by **aosmond** (accept) | — | 2026-01-10 00:04:51 UTC by **aosmond** | — |
| 130 | [D278674](https://phabricator.services.mozilla.com/D278674) | ArnaudBienner | 2026-01-12 17:12:29 UTC | 2026-01-12 17:12:40 UTC | 2026-01-19 20:23:23 UTC by **karlt** (accept) | 7.13 d | 2026-01-19 20:23:23 UTC by **karlt** | 7.13 d |
| 131 | [D278686](https://phabricator.services.mozilla.com/D278686) | aosmond | 2026-01-12 18:58:56 UTC | 2026-01-12 18:59:14 UTC | 2026-01-13 15:14:01 UTC by **padenot** (accept) | 20.2 h | 2026-01-13 15:14:01 UTC by **padenot** | 20.2 h |
| 132 | [D278710](https://phabricator.services.mozilla.com/D278710) | aosmond | 2026-01-12 22:10:06 UTC | 2026-01-12 22:11:38 UTC | 2026-01-13 15:14:38 UTC by **padenot** (accept) | 17.1 h | 2026-01-13 15:14:38 UTC by **padenot** | 17.1 h |
| 133 | [D278729](https://phabricator.services.mozilla.com/D278729) | aosmond | 2026-01-13 01:40:50 UTC | 2026-01-13 01:40:59 UTC | 2026-01-13 14:11:11 UTC by **padenot** (accept) | 12.5 h | 2026-01-13 14:11:11 UTC by **padenot** | 12.5 h |
| 134 | [D278731](https://phabricator.services.mozilla.com/D278731) | aosmond | 2026-01-13 02:13:59 UTC | 2026-01-13 02:14:09 UTC | 2026-01-13 14:10:59 UTC by **padenot** (accept) | 11.9 h | 2026-01-13 14:10:59 UTC by **padenot** | 11.9 h |
| 135 | [D278771](https://phabricator.services.mozilla.com/D278771) | — | — | 2026-01-14 00:28:30 UTC | 2026-01-14 19:22:44 UTC by **alwu** (accept) | 18.9 h | 2026-01-14 19:22:44 UTC by **alwu** | 18.9 h |
| 136 | [D278786](https://phabricator.services.mozilla.com/D278786) | sergesanspaille | 2026-01-13 13:40:53 UTC | 2026-01-13 13:41:00 UTC | 2026-01-14 14:45:06 UTC by **padenot** (accept) | 1.04 d | 2026-01-14 14:45:06 UTC by **padenot** | 1.04 d |
| 137 | [D279132](https://phabricator.services.mozilla.com/D279132) | sergesanspaille | 2026-01-15 12:34:04 UTC | 2026-01-15 12:34:26 UTC | 2026-01-15 13:07:45 UTC by **padenot** (accept) | 0.6 h | 2026-01-15 13:07:45 UTC by **padenot** | 0.6 h |
| 138 | [D279266](https://phabricator.services.mozilla.com/D279266) | karlt | 2026-01-16 08:52:58 UTC | — | — | — | — | — |
| 139 | [D279314](https://phabricator.services.mozilla.com/D279314) | Standard8 | 2026-01-16 14:11:42 UTC | 2026-01-16 14:12:13 UTC | 2026-01-19 19:03:43 UTC by **aosmond** (accept) | 3.20 d | 2026-01-19 19:03:43 UTC by **aosmond** | 3.20 d |
| 140 | [D279321](https://phabricator.services.mozilla.com/D279321) | Standard8 | 2026-01-16 14:12:29 UTC | — | — | — | — | — |
| 141 | [D279342](https://phabricator.services.mozilla.com/D279342) | florian | 2026-01-16 16:24:33 UTC | — | — | — | — | — |
| 142 | [D279470](https://phabricator.services.mozilla.com/D279470) | jstutte | 2026-01-18 11:13:52 UTC | — | — | — | — | — |
| 143 | [D279500](https://phabricator.services.mozilla.com/D279500) | jstutte | 2026-01-19 10:27:59 UTC | — | — | — | — | — |
| 144 | [D279521](https://phabricator.services.mozilla.com/D279521) | emilio | 2026-01-19 13:44:50 UTC | — | 2026-01-19 14:51:21 UTC by **padenot** (accept) | — | 2026-01-19 14:51:21 UTC by **padenot** | — |
| 145 | [D279554](https://phabricator.services.mozilla.com/D279554) | tmarble | 2026-01-19 18:03:55 UTC | — | — | — | — | — |
| 146 | [D279724](https://phabricator.services.mozilla.com/D279724) | YuK | 2026-01-20 16:52:54 UTC | — | 2026-01-20 17:54:59 UTC by **aosmond** (request-changes) | — | 2026-01-21 19:09:10 UTC by **alwu** | — |
| 147 | [D279751](https://phabricator.services.mozilla.com/D279751) | — | — | — | 2026-01-21 00:21:26 UTC by **alwu** (comment) | — | 2026-02-02 05:30:25 UTC by **karlt** | — |
| 148 | [D279869](https://phabricator.services.mozilla.com/D279869) | pehrsons | 2026-01-21 14:31:17 UTC | — | — | — | — | — |
| 149 | [D279870](https://phabricator.services.mozilla.com/D279870) | pehrsons | 2026-01-21 14:31:26 UTC | — | — | — | — | — |
| 150 | [D279871](https://phabricator.services.mozilla.com/D279871) | pehrsons | 2026-01-21 14:31:33 UTC | — | — | — | — | — |
| 151 | [D279872](https://phabricator.services.mozilla.com/D279872) | pehrsons | 2026-01-21 14:31:39 UTC | — | — | — | — | — |
| 152 | [D279879](https://phabricator.services.mozilla.com/D279879) | pehrsons | 2026-01-21 14:51:59 UTC | — | 2026-01-29 20:22:46 UTC by **karlt** (comment) | — | — | — |
| 153 | [D279880](https://phabricator.services.mozilla.com/D279880) | pehrsons | 2026-01-21 14:52:08 UTC | — | — | — | — | — |
| 154 | [D280057](https://phabricator.services.mozilla.com/D280057) | ArnaudBienner | 2026-01-22 15:17:18 UTC | 2026-01-22 15:17:24 UTC | 2026-01-22 19:17:38 UTC by **karlt** (accept) | 4.0 h | 2026-01-22 19:17:38 UTC by **karlt** | 4.0 h |
| 155 | [D280073](https://phabricator.services.mozilla.com/D280073) | ArnaudBienner | 2026-01-22 16:27:26 UTC | 2026-01-22 16:27:34 UTC | 2026-01-22 19:14:10 UTC by **karlt** (accept) | 2.8 h | 2026-01-22 19:14:10 UTC by **karlt** | 2.8 h |
| 156 | [D280116](https://phabricator.services.mozilla.com/D280116) | alwu | 2026-01-22 21:10:24 UTC | — | — | — | — | — |
| 157 | [D280171](https://phabricator.services.mozilla.com/D280171) | — | — | — | — | — | — | — |
| 158 | [D280248](https://phabricator.services.mozilla.com/D280248) | sergesanspaille | 2026-01-23 14:54:21 UTC | — | — | — | — | — |
| 159 | [D280366](https://phabricator.services.mozilla.com/D280366) | jolin | 2026-01-24 20:02:24 UTC | 2026-01-24 20:02:34 UTC | 2026-01-26 23:43:55 UTC by **alwu** (accept) | 2.15 d | 2026-01-26 23:43:55 UTC by **alwu** | 2.15 d |
| 160 | [D280379](https://phabricator.services.mozilla.com/D280379) | — | — | — | — | — | — | — |
| 161 | [D280571](https://phabricator.services.mozilla.com/D280571) | pehrsons | 2026-01-27 11:01:51 UTC | — | — | — | — | — |
| 162 | [D280572](https://phabricator.services.mozilla.com/D280572) | pehrsons | 2026-01-27 11:02:00 UTC | — | 2026-01-29 19:38:46 UTC by **karlt** (accept) | — | 2026-01-29 19:38:46 UTC by **karlt** | — |
| 163 | [D280573](https://phabricator.services.mozilla.com/D280573) | pehrsons | 2026-01-27 11:02:06 UTC | — | — | — | — | — |
| 164 | [D280574](https://phabricator.services.mozilla.com/D280574) | pehrsons | 2026-01-27 11:02:22 UTC | — | — | — | — | — |
| 165 | [D281037](https://phabricator.services.mozilla.com/D281037) | — | — | 2026-01-29 23:25:14 UTC | 2026-02-03 23:43:47 UTC by **alwu** (comment) | 5.01 d | 2026-02-05 18:32:27 UTC by **chunmin** | 6.80 d |
| 166 | [D281038](https://phabricator.services.mozilla.com/D281038) | — | — | 2026-01-29 23:25:17 UTC | 2026-02-05 18:32:31 UTC by **chunmin** (accept) | 6.80 d | 2026-02-05 18:32:31 UTC by **chunmin** | 6.80 d |
| 167 | [D281039](https://phabricator.services.mozilla.com/D281039) | — | — | — | 2026-01-29 19:22:56 UTC by **alwu** (comment) | — | 2026-02-05 18:32:34 UTC by **chunmin** | — |
| 168 | [D281040](https://phabricator.services.mozilla.com/D281040) | — | — | — | 2026-01-29 19:25:37 UTC by **alwu** (comment) | — | 2026-02-05 18:32:30 UTC by **chunmin** | — |
| 169 | [D281052](https://phabricator.services.mozilla.com/D281052) | aosmond | 2026-01-29 19:29:31 UTC | 2026-01-29 19:30:15 UTC | 2026-01-29 21:53:25 UTC by **azebrowski** (accept) | 2.4 h | 2026-01-29 21:53:25 UTC by **azebrowski** | 2.4 h |
| 170 | [D281058](https://phabricator.services.mozilla.com/D281058) | aosmond | 2026-01-29 19:52:12 UTC | 2026-01-29 19:53:33 UTC | 2026-01-29 22:54:22 UTC by **alwu** (accept) | 3.0 h | 2026-01-29 22:54:22 UTC by **alwu** | 3.0 h |
| 171 | [D281112](https://phabricator.services.mozilla.com/D281112) | nika | 2026-01-30 00:29:12 UTC | — | — | — | — | — |
| 172 | [D281149](https://phabricator.services.mozilla.com/D281149) | — | — | — | — | — | — | — |
| 173 | [D281171](https://phabricator.services.mozilla.com/D281171) | pehrsons | 2026-01-30 13:05:20 UTC | — | — | — | — | — |
| 174 | [D281172](https://phabricator.services.mozilla.com/D281172) | pehrsons | 2026-01-30 13:16:16 UTC | — | — | — | — | — |
| 175 | [D281224](https://phabricator.services.mozilla.com/D281224) | sergesanspaille | 2026-01-30 15:16:09 UTC | 2026-01-30 15:16:19 UTC | 2026-01-30 15:36:39 UTC by **padenot** (accept) | 0.3 h | 2026-01-30 15:36:39 UTC by **padenot** | 0.3 h |
| 176 | [D281249](https://phabricator.services.mozilla.com/D281249) | chunmin | 2026-01-30 18:57:51 UTC | 2026-01-30 19:02:21 UTC | 2026-01-30 19:08:03 UTC by **alwu** (accept) | 0.1 h | 2026-01-30 19:08:03 UTC by **alwu** | 0.1 h |
| 177 | [D281250](https://phabricator.services.mozilla.com/D281250) | chunmin | 2026-01-30 18:57:55 UTC | — | 2026-01-30 19:07:44 UTC by **alwu** (accept) | — | 2026-01-30 19:07:44 UTC by **alwu** | — |
| 178 | [D281454](https://phabricator.services.mozilla.com/D281454) | pehrsons | 2026-02-02 14:45:09 UTC | — | 2026-02-16 06:11:55 UTC by **karlt** (accept) | — | 2026-02-16 06:11:55 UTC by **karlt** | — |
| 179 | [D281484](https://phabricator.services.mozilla.com/D281484) | cpeterson | 2026-02-02 16:54:18 UTC | — | 2026-02-03 13:13:12 UTC by **padenot** (accept) | — | 2026-02-03 13:13:12 UTC by **padenot** | — |
| 180 | [D281547](https://phabricator.services.mozilla.com/D281547) | chunmin | 2026-02-02 22:59:02 UTC | 2026-02-02 23:02:44 UTC | 2026-02-03 14:31:01 UTC by **padenot** (accept) | 15.5 h | 2026-02-03 14:31:01 UTC by **padenot** | 15.5 h |
| 181 | [D281548](https://phabricator.services.mozilla.com/D281548) | chunmin | 2026-02-02 22:59:06 UTC | — | 2026-02-03 14:30:27 UTC by **padenot** (accept) | — | 2026-02-03 14:30:27 UTC by **padenot** | — |
| 182 | [D281549](https://phabricator.services.mozilla.com/D281549) | chunmin | 2026-02-02 22:59:09 UTC | 2026-02-02 23:03:35 UTC | 2026-02-03 14:30:07 UTC by **padenot** (accept) | 15.4 h | 2026-02-03 14:30:07 UTC by **padenot** | 15.4 h |
| 183 | [D281550](https://phabricator.services.mozilla.com/D281550) | chunmin | 2026-02-02 22:59:12 UTC | 2026-02-02 23:03:57 UTC | 2026-02-03 14:29:52 UTC by **padenot** (accept) | 15.4 h | 2026-02-03 14:29:52 UTC by **padenot** | 15.4 h |
| 184 | [D281623](https://phabricator.services.mozilla.com/D281623) | aosmond | 2026-02-03 15:22:56 UTC | 2026-02-03 15:24:39 UTC | 2026-02-03 16:58:32 UTC by **padenot** (accept) | 1.6 h | 2026-02-03 16:58:32 UTC by **padenot** | 1.6 h |
| 185 | [D281688](https://phabricator.services.mozilla.com/D281688) | aosmond | 2026-02-03 22:11:13 UTC | 2026-02-03 22:11:41 UTC | 2026-02-04 19:18:45 UTC by **jolin** (accept) | 21.1 h | 2026-02-04 19:18:45 UTC by **jolin** | 21.1 h |
| 186 | [D281715](https://phabricator.services.mozilla.com/D281715) | alwu | 2026-02-04 02:49:14 UTC | — | — | — | — | — |
| 187 | [D281716](https://phabricator.services.mozilla.com/D281716) | alwu | 2026-02-04 02:49:20 UTC | — | — | — | — | — |
| 188 | [D281769](https://phabricator.services.mozilla.com/D281769) | — | — | — | — | — | — | — |
| 189 | [D282114](https://phabricator.services.mozilla.com/D282114) | alwu | 2026-02-06 08:03:38 UTC | — | — | — | — | — |
| 190 | [D282157](https://phabricator.services.mozilla.com/D282157) | — | — | — | — | — | — | — |
| 191 | [D282158](https://phabricator.services.mozilla.com/D282158) | — | — | — | — | — | — | — |
| 192 | [D282171](https://phabricator.services.mozilla.com/D282171) | — | — | — | — | — | — | — |
| 193 | [D282192](https://phabricator.services.mozilla.com/D282192) | — | — | — | — | — | — | — |
| 194 | [D282240](https://phabricator.services.mozilla.com/D282240) | jolin | 2026-02-06 22:31:40 UTC | 2026-02-06 22:31:51 UTC | 2026-02-09 03:34:25 UTC by **karlt** (accept) | 2.21 d | 2026-02-09 03:34:25 UTC by **karlt** | 2.21 d |
| 195 | [D282346](https://phabricator.services.mozilla.com/D282346) | — | — | — | — | — | — | — |
| 196 | [D282347](https://phabricator.services.mozilla.com/D282347) | — | — | — | — | — | — | — |
| 197 | [D282348](https://phabricator.services.mozilla.com/D282348) | — | — | — | — | — | — | — |
| 198 | [D282349](https://phabricator.services.mozilla.com/D282349) | — | — | — | — | — | — | — |
| 199 | [D282360](https://phabricator.services.mozilla.com/D282360) | — | — | — | — | — | — | — |
| 200 | [D282367](https://phabricator.services.mozilla.com/D282367) | — | — | — | — | — | — | — |
| 201 | [D282369](https://phabricator.services.mozilla.com/D282369) | — | — | — | — | — | — | — |
| 202 | [D282370](https://phabricator.services.mozilla.com/D282370) | — | — | — | — | — | — | — |
| 203 | [D282392](https://phabricator.services.mozilla.com/D282392) | — | — | — | — | — | — | — |
| 204 | [D282394](https://phabricator.services.mozilla.com/D282394) | — | — | — | — | — | — | — |
| 205 | [D282395](https://phabricator.services.mozilla.com/D282395) | — | — | — | — | — | — | — |
| 206 | [D282396](https://phabricator.services.mozilla.com/D282396) | padenot | 2026-02-09 14:55:12 UTC | — | — | — | — | — |
| 207 | [D282397](https://phabricator.services.mozilla.com/D282397) | — | — | — | — | — | — | — |
| 208 | [D282414](https://phabricator.services.mozilla.com/D282414) | — | — | — | — | — | — | — |
| 209 | [D282419](https://phabricator.services.mozilla.com/D282419) | — | — | — | — | — | — | — |
| 210 | [D282420](https://phabricator.services.mozilla.com/D282420) | — | — | — | — | — | — | — |
| 211 | [D282422](https://phabricator.services.mozilla.com/D282422) | — | — | — | — | — | — | — |
| 212 | [D282427](https://phabricator.services.mozilla.com/D282427) | — | — | — | — | — | — | — |
| 213 | [D282431](https://phabricator.services.mozilla.com/D282431) | — | — | — | — | — | — | — |
| 214 | [D282432](https://phabricator.services.mozilla.com/D282432) | — | — | — | — | — | — | — |
| 215 | [D282786](https://phabricator.services.mozilla.com/D282786) | — | — | — | — | — | — | — |
| 216 | [D282878](https://phabricator.services.mozilla.com/D282878) | jolin | 2026-02-11 19:01:41 UTC | 2026-02-11 19:26:50 UTC | 2026-02-11 19:29:26 UTC by **alwu** (accept) | 0.0 h | 2026-02-11 19:29:26 UTC by **alwu** | 0.0 h |
| 217 | [D282916](https://phabricator.services.mozilla.com/D282916) | — | — | — | — | — | — | — |
| 218 | [D282918](https://phabricator.services.mozilla.com/D282918) | — | — | — | — | — | — | — |
| 219 | [D282927](https://phabricator.services.mozilla.com/D282927) | — | — | — | — | — | — | — |
| 220 | [D282928](https://phabricator.services.mozilla.com/D282928) | — | — | — | — | — | — | — |
| 221 | [D282953](https://phabricator.services.mozilla.com/D282953) | — | — | — | — | — | — | — |
| 222 | [D282994](https://phabricator.services.mozilla.com/D282994) | sergesanspaille | 2026-02-12 09:24:13 UTC | — | — | — | — | — |
| 223 | [D283106](https://phabricator.services.mozilla.com/D283106) | — | — | — | — | — | — | — |
| 224 | [D283178](https://phabricator.services.mozilla.com/D283178) | — | — | — | — | — | — | — |
| 225 | [D283335](https://phabricator.services.mozilla.com/D283335) | — | — | — | — | — | — | — |
| 226 | [D283336](https://phabricator.services.mozilla.com/D283336) | padenot | 2026-02-13 18:04:35 UTC | — | 2026-02-13 18:28:56 UTC by **chunmin** (accept) | — | 2026-02-13 18:28:56 UTC by **chunmin** | — |
| 227 | [D283403](https://phabricator.services.mozilla.com/D283403) | alwu | 2026-02-14 02:20:13 UTC | 2026-02-14 02:20:29 UTC | 2026-02-16 17:45:06 UTC by **padenot** (accept) | 2.64 d | 2026-02-16 17:45:06 UTC by **padenot** | 2.64 d |
| 228 | [D283433](https://phabricator.services.mozilla.com/D283433) | — | — | — | — | — | — | — |
| 229 | [D283461](https://phabricator.services.mozilla.com/D283461) | anutrix | 2026-02-15 16:58:22 UTC | 2026-02-15 16:58:33 UTC | 2026-02-16 18:23:26 UTC by **padenot** (accept) | 1.06 d | 2026-02-16 18:23:26 UTC by **padenot** | 1.06 d |
| 230 | [D283509](https://phabricator.services.mozilla.com/D283509) | karlt | 2026-02-16 08:05:48 UTC | — | 2026-02-16 12:36:27 UTC by **padenot** (accept) | — | 2026-02-16 12:36:27 UTC by **padenot** | — |
| 231 | [D283510](https://phabricator.services.mozilla.com/D283510) | — | — | — | — | — | — | — |
| 232 | [D283511](https://phabricator.services.mozilla.com/D283511) | — | — | — | — | — | — | — |
| 233 | [D283512](https://phabricator.services.mozilla.com/D283512) | — | — | — | — | — | — | — |
| 234 | [D283654](https://phabricator.services.mozilla.com/D283654) | karlt | 2026-02-17 08:53:07 UTC | — | 2026-02-17 09:27:36 UTC by **padenot** (accept) | — | 2026-02-17 09:27:36 UTC by **padenot** | — |
| 235 | [D283813](https://phabricator.services.mozilla.com/D283813) | — | — | — | — | — | — | — |
| 236 | [D283814](https://phabricator.services.mozilla.com/D283814) | — | — | — | — | — | — | — |
| 237 | [D283821](https://phabricator.services.mozilla.com/D283821) | karlt | 2026-02-18 04:24:13 UTC | 2026-02-18 04:24:38 UTC | 2026-02-18 08:18:44 UTC by **padenot** (accept) | 3.9 h | 2026-02-18 08:18:44 UTC by **padenot** | 3.9 h |
| 238 | [D283824](https://phabricator.services.mozilla.com/D283824) | tnikkel | 2026-02-18 05:30:11 UTC | — | 2026-02-18 13:13:53 UTC by **aosmond** (accept) | — | 2026-02-18 13:13:53 UTC by **aosmond** | — |
| 239 | [D283838](https://phabricator.services.mozilla.com/D283838) | padenot | 2026-02-18 09:34:11 UTC | 2026-02-18 09:36:12 UTC | 2026-02-19 03:44:42 UTC by **karlt** (accept) | 18.1 h | 2026-02-19 03:44:42 UTC by **karlt** | 18.1 h |
| 240 | [D283860](https://phabricator.services.mozilla.com/D283860) | padenot | 2026-02-18 12:55:04 UTC | — | — | — | — | — |
| 241 | [D283900](https://phabricator.services.mozilla.com/D283900) | — | — | — | — | — | — | — |
| 242 | [D284094](https://phabricator.services.mozilla.com/D284094) | padenot | 2026-02-19 15:53:28 UTC | — | 2026-02-19 19:05:20 UTC by **alwu** (accept) | — | 2026-02-19 19:05:20 UTC by **alwu** | — |
| 243 | [D284095](https://phabricator.services.mozilla.com/D284095) | padenot | 2026-02-19 15:54:20 UTC | — | 2026-02-19 22:55:37 UTC by **chunmin** (accept) | — | 2026-02-19 22:55:37 UTC by **chunmin** | — |
| 244 | [D284103](https://phabricator.services.mozilla.com/D284103) | padenot | 2026-02-19 16:52:57 UTC | — | 2026-02-19 22:53:26 UTC by **chunmin** (accept) | — | 2026-02-19 22:53:26 UTC by **chunmin** | — |
| 245 | [D284120](https://phabricator.services.mozilla.com/D284120) | padenot | 2026-02-19 17:54:38 UTC | — | 2026-02-19 23:14:01 UTC by **chunmin** (accept) | — | 2026-02-19 23:14:01 UTC by **chunmin** | — |
| 246 | [D284123](https://phabricator.services.mozilla.com/D284123) | padenot | 2026-02-19 18:11:16 UTC | — | 2026-02-19 19:28:00 UTC by **alwu** (accept) | — | 2026-02-19 19:28:00 UTC by **alwu** | — |
| 247 | [D284196](https://phabricator.services.mozilla.com/D284196) | — | — | 2026-02-20 02:09:42 UTC | 2026-02-20 12:30:56 UTC by **padenot** (accept) | 10.4 h | 2026-02-20 12:30:56 UTC by **padenot** | 10.4 h |
| 248 | [D284197](https://phabricator.services.mozilla.com/D284197) | — | — | 2026-02-20 02:08:49 UTC | 2026-02-20 12:30:27 UTC by **padenot** (accept) | 10.4 h | 2026-02-20 12:30:27 UTC by **padenot** | 10.4 h |
| 249 | [D284267](https://phabricator.services.mozilla.com/D284267) | sergesanspaille | 2026-02-20 14:32:44 UTC | — | 2026-02-20 14:36:02 UTC by **padenot** (accept) | — | 2026-02-20 14:36:02 UTC by **padenot** | — |
| 250 | [D284335](https://phabricator.services.mozilla.com/D284335) | alwu | 2026-02-20 21:40:57 UTC | 2026-02-20 21:43:56 UTC | 2026-02-20 22:07:19 UTC by **aosmond** (accept) | 0.4 h | 2026-02-20 22:07:19 UTC by **aosmond** | 0.4 h |
| 251 | [D284339](https://phabricator.services.mozilla.com/D284339) | alwu | 2026-02-20 22:03:33 UTC | 2026-02-20 22:04:10 UTC | 2026-02-23 15:14:25 UTC by **padenot** (accept) | 2.72 d | 2026-02-23 15:14:25 UTC by **padenot** | 2.72 d |
| 252 | [D284355](https://phabricator.services.mozilla.com/D284355) | — | — | 2026-02-23 23:12:30 UTC | 2026-02-24 13:16:35 UTC by **padenot** (accept) | 14.1 h | 2026-02-24 13:16:35 UTC by **padenot** | 14.1 h |
| 253 | [D284358](https://phabricator.services.mozilla.com/D284358) | — | — | — | — | — | — | — |
| 254 | [D284373](https://phabricator.services.mozilla.com/D284373) | sergesanspaille | 2026-02-21 09:54:26 UTC | — | 2026-02-23 15:17:53 UTC by **padenot** (accept) | — | 2026-02-23 15:17:53 UTC by **padenot** | — |
| 255 | [D284397](https://phabricator.services.mozilla.com/D284397) | iamanshulmalik | 2026-02-22 10:54:35 UTC | — | — | — | — | — |
| 256 | [D284461](https://phabricator.services.mozilla.com/D284461) | — | — | — | — | — | — | — |
| 257 | [D284567](https://phabricator.services.mozilla.com/D284567) | chunmin | 2026-02-23 23:12:32 UTC | 2026-02-23 23:13:54 UTC | 2026-02-24 13:16:46 UTC by **padenot** (accept) | 14.0 h | 2026-02-24 13:16:46 UTC by **padenot** | 14.0 h |
| 258 | [D284650](https://phabricator.services.mozilla.com/D284650) | pehrsons | 2026-02-24 13:48:10 UTC | — | — | — | — | — |
| 259 | [D284752](https://phabricator.services.mozilla.com/D284752) | bobowen | 2026-02-24 21:34:00 UTC | 2026-02-24 21:34:12 UTC | 2026-03-24 20:49:40 UTC by **aosmond** (accept) | 27.97 d | 2026-03-24 20:49:40 UTC by **aosmond** | 27.97 d |
| 260 | [D284761](https://phabricator.services.mozilla.com/D284761) | — | — | — | — | — | — | — |
| 261 | [D284809](https://phabricator.services.mozilla.com/D284809) | pehrsons | 2026-02-25 08:47:39 UTC | — | — | — | — | — |
| 262 | [D284849](https://phabricator.services.mozilla.com/D284849) | — | — | — | — | — | — | — |
| 263 | [D284972](https://phabricator.services.mozilla.com/D284972) | — | — | — | — | — | — | — |
| 264 | [D285053](https://phabricator.services.mozilla.com/D285053) | — | — | 2026-02-26 15:28:01 UTC | 2026-03-09 18:08:19 UTC by **padenot** (accept) | 11.11 d | 2026-03-09 18:08:19 UTC by **padenot** | 11.11 d |
| 265 | [D285106](https://phabricator.services.mozilla.com/D285106) | — | — | 2026-03-02 22:40:18 UTC | 2026-03-03 19:56:26 UTC by **jolin** (accept) | 21.3 h | 2026-03-03 19:56:26 UTC by **jolin** | 21.3 h |
| 266 | [D285108](https://phabricator.services.mozilla.com/D285108) | — | — | 2026-03-02 22:06:07 UTC | 2026-03-03 20:03:17 UTC by **jolin** (accept) | 22.0 h | 2026-03-03 20:03:17 UTC by **jolin** | 22.0 h |
| 267 | [D285109](https://phabricator.services.mozilla.com/D285109) | — | — | 2026-03-02 22:06:09 UTC | 2026-03-03 20:17:47 UTC by **jolin** (accept) | 22.2 h | 2026-03-03 20:17:47 UTC by **jolin** | 22.2 h |
| 268 | [D285126](https://phabricator.services.mozilla.com/D285126) | — | — | — | 2026-02-27 10:13:10 UTC by **padenot** (accept) | — | 2026-02-27 10:13:10 UTC by **padenot** | — |
| 269 | [D285205](https://phabricator.services.mozilla.com/D285205) | — | — | — | — | — | — | — |
| 270 | [D285364](https://phabricator.services.mozilla.com/D285364) | — | — | — | — | — | — | — |
| 271 | [D285602](https://phabricator.services.mozilla.com/D285602) | chunmin | 2026-03-02 21:55:38 UTC | — | 2026-03-04 04:48:35 UTC by **karlt** (accept) | — | 2026-03-04 04:48:35 UTC by **karlt** | — |
| 272 | [D285608](https://phabricator.services.mozilla.com/D285608) | chunmin | 2026-03-02 22:04:49 UTC | 2026-03-02 23:33:23 UTC | 2026-03-03 12:25:38 UTC by **padenot** (accept) | 12.9 h | 2026-03-03 12:25:38 UTC by **padenot** | 12.9 h |
| 273 | [D285648](https://phabricator.services.mozilla.com/D285648) | — | — | — | — | — | — | — |
| 274 | [D285674](https://phabricator.services.mozilla.com/D285674) | sergesanspaille | 2026-03-03 09:33:28 UTC | 2026-03-03 09:34:08 UTC | 2026-03-03 14:48:17 UTC by **padenot** (accept) | 5.2 h | 2026-03-03 14:48:17 UTC by **padenot** | 5.2 h |
| 275 | [D285683](https://phabricator.services.mozilla.com/D285683) | — | — | — | — | — | — | — |
| 276 | [D285684](https://phabricator.services.mozilla.com/D285684) | — | — | — | — | — | — | — |
| 277 | [D285694](https://phabricator.services.mozilla.com/D285694) | anba | 2026-03-03 10:31:29 UTC | 2026-03-03 10:31:38 UTC | 2026-03-03 11:02:24 UTC by **padenot** (accept) | 0.5 h | 2026-03-03 11:02:24 UTC by **padenot** | 0.5 h |
| 278 | [D285769](https://phabricator.services.mozilla.com/D285769) | padenot | 2026-03-03 16:26:41 UTC | — | 2026-03-09 04:42:18 UTC by **karlt** (accept) | — | 2026-03-09 04:42:18 UTC by **karlt** | — |
| 279 | [D285794](https://phabricator.services.mozilla.com/D285794) | padenot | 2026-03-03 17:24:07 UTC | — | 2026-03-09 04:08:25 UTC by **karlt** (accept) | — | 2026-03-09 04:08:25 UTC by **karlt** | — |
| 280 | [D285835](https://phabricator.services.mozilla.com/D285835) | jmoss | 2026-03-03 20:10:23 UTC | — | — | — | — | — |
| 281 | [D285891](https://phabricator.services.mozilla.com/D285891) | — | — | — | — | — | — | — |
| 282 | [D285896](https://phabricator.services.mozilla.com/D285896) | — | — | — | 2026-03-04 06:05:48 UTC by **chunmin** (comment) | — | 2026-03-09 10:30:02 UTC by **padenot** | — |
| 283 | [D285897](https://phabricator.services.mozilla.com/D285897) | — | — | 2026-03-05 19:39:01 UTC | 2026-03-09 10:30:31 UTC by **padenot** (accept) | 3.62 d | 2026-03-09 10:30:31 UTC by **padenot** | 3.62 d |
| 284 | [D285931](https://phabricator.services.mozilla.com/D285931) | smolnar | 2026-03-04 08:20:44 UTC | 2026-03-04 08:22:08 UTC | 2026-03-04 12:23:33 UTC by **padenot** (accept) | 4.0 h | 2026-03-04 12:23:33 UTC by **padenot** | 4.0 h |
| 285 | [D286014](https://phabricator.services.mozilla.com/D286014) | — | — | 2026-03-04 14:16:40 UTC | 2026-03-04 14:46:32 UTC by **padenot** (accept) | 0.5 h | 2026-03-04 14:46:32 UTC by **padenot** | 0.5 h |
| 286 | [D286105](https://phabricator.services.mozilla.com/D286105) | — | — | — | — | — | — | — |
| 287 | [D286106](https://phabricator.services.mozilla.com/D286106) | — | — | — | — | — | — | — |
| 288 | [D286108](https://phabricator.services.mozilla.com/D286108) | — | — | — | — | — | — | — |
| 289 | [D286158](https://phabricator.services.mozilla.com/D286158) | — | — | — | — | — | — | — |
| 290 | [D286161](https://phabricator.services.mozilla.com/D286161) | — | — | — | — | — | — | — |
| 291 | [D286225](https://phabricator.services.mozilla.com/D286225) | — | — | — | — | — | — | — |
| 292 | [D286311](https://phabricator.services.mozilla.com/D286311) | anba | 2026-03-05 17:14:15 UTC | — | — | — | — | — |
| 293 | [D286320](https://phabricator.services.mozilla.com/D286320) | anba | 2026-03-05 17:17:05 UTC | — | — | — | — | — |
| 294 | [D286350](https://phabricator.services.mozilla.com/D286350) | — | — | 2026-03-05 19:39:03 UTC | 2026-03-09 10:32:12 UTC by **padenot** (accept) | 3.62 d | 2026-03-09 10:32:12 UTC by **padenot** | 3.62 d |
| 295 | [D286351](https://phabricator.services.mozilla.com/D286351) | — | — | 2026-03-05 19:39:05 UTC | 2026-03-09 17:49:15 UTC by **padenot** (accept) | 3.92 d | 2026-03-09 17:49:15 UTC by **padenot** | 3.92 d |
| 296 | [D286440](https://phabricator.services.mozilla.com/D286440) | iamanshulmalik | 2026-03-06 03:24:33 UTC | — | — | — | — | — |
| 297 | [D286504](https://phabricator.services.mozilla.com/D286504) | chunmin | 2026-03-06 21:59:24 UTC | 2026-03-06 22:00:29 UTC | 2026-03-09 11:29:58 UTC by **padenot** (accept) | 2.56 d | 2026-03-09 11:29:58 UTC by **padenot** | 2.56 d |
| 298 | [D286533](https://phabricator.services.mozilla.com/D286533) | RyanVM | 2026-03-07 15:24:30 UTC | 2026-03-07 15:25:26 UTC | 2026-03-09 17:48:37 UTC by **padenot** (accept) | 2.10 d | 2026-03-09 17:48:37 UTC by **padenot** | 2.10 d |
| 299 | [D286672](https://phabricator.services.mozilla.com/D286672) | padenot | 2026-03-09 13:45:22 UTC | — | 2026-03-10 17:55:19 UTC by **jolin** (accept) | — | 2026-03-10 17:55:19 UTC by **jolin** | — |
| 300 | [D286673](https://phabricator.services.mozilla.com/D286673) | pehrsons | 2026-03-09 13:49:01 UTC | — | — | — | — | — |
| 301 | [D286756](https://phabricator.services.mozilla.com/D286756) | padenot | 2026-03-09 18:59:12 UTC | — | 2026-03-11 18:24:27 UTC by **alwu** (accept) | — | 2026-03-11 18:24:27 UTC by **alwu** | — |
| 302 | [D286759](https://phabricator.services.mozilla.com/D286759) | — | — | — | 2026-03-16 23:29:06 UTC by **alwu** (request-changes) | — | 2026-03-19 22:10:10 UTC by **alwu** | — |
| 303 | [D286844](https://phabricator.services.mozilla.com/D286844) | jolin | 2026-03-10 08:34:30 UTC | 2026-03-10 08:35:42 UTC | 2026-03-11 14:13:48 UTC by **padenot** (accept) | 1.23 d | 2026-03-11 14:13:48 UTC by **padenot** | 1.23 d |
| 304 | [D286866](https://phabricator.services.mozilla.com/D286866) | pehrsons | 2026-03-10 11:17:17 UTC | — | — | — | — | — |
| 305 | [D286868](https://phabricator.services.mozilla.com/D286868) | — | — | — | — | — | — | — |
| 306 | [D286878](https://phabricator.services.mozilla.com/D286878) | jari | 2026-03-10 13:30:06 UTC | — | 2026-03-10 13:34:44 UTC by **padenot** (accept) | — | 2026-03-10 13:34:44 UTC by **padenot** | — |
| 307 | [D286894](https://phabricator.services.mozilla.com/D286894) | pehrsons | 2026-03-10 14:30:13 UTC | — | — | — | — | — |
| 308 | [D286914](https://phabricator.services.mozilla.com/D286914) | aosmond | 2026-03-10 15:28:10 UTC | 2026-03-10 15:30:15 UTC | 2026-03-10 17:23:56 UTC by **jolin** (accept) | 1.9 h | 2026-03-10 17:23:56 UTC by **jolin** | 1.9 h |
| 309 | [D286960](https://phabricator.services.mozilla.com/D286960) | padenot | 2026-03-10 17:59:06 UTC | — | — | — | — | — |
| 310 | [D287078](https://phabricator.services.mozilla.com/D287078) | — | — | — | — | — | — | — |
| 311 | [D287100](https://phabricator.services.mozilla.com/D287100) | pehrsons | 2026-03-11 11:55:21 UTC | — | — | — | — | — |
| 312 | [D287116](https://phabricator.services.mozilla.com/D287116) | — | — | — | — | — | — | — |
| 313 | [D287117](https://phabricator.services.mozilla.com/D287117) | — | — | — | — | — | — | — |
| 314 | [D287118](https://phabricator.services.mozilla.com/D287118) | — | — | — | — | — | — | — |
| 315 | [D287193](https://phabricator.services.mozilla.com/D287193) | padenot | 2026-03-11 18:05:29 UTC | — | — | — | — | — |
| 316 | [D287209](https://phabricator.services.mozilla.com/D287209) | jolin | 2026-03-11 19:27:07 UTC | — | 2026-03-12 02:05:22 UTC by **alwu** (accept) | — | 2026-03-12 02:05:22 UTC by **alwu** | — |
| 317 | [D287396](https://phabricator.services.mozilla.com/D287396) | — | — | — | — | — | — | — |
| 318 | [D287507](https://phabricator.services.mozilla.com/D287507) | — | — | — | — | — | — | — |
| 319 | [D287540](https://phabricator.services.mozilla.com/D287540) | sergesanspaille | 2026-03-13 10:35:26 UTC | 2026-03-13 10:35:33 UTC | 2026-03-13 17:55:27 UTC by **padenot** (request-changes) | 7.3 h | 2026-03-16 14:58:38 UTC by **padenot** | 3.18 d |
| 320 | [D287544](https://phabricator.services.mozilla.com/D287544) | bobowen | 2026-03-13 11:04:49 UTC | 2026-03-13 11:04:54 UTC | 2026-03-24 20:49:05 UTC by **aosmond** (accept) | 11.41 d | 2026-03-24 20:49:05 UTC by **aosmond** | 11.41 d |
| 321 | [D287561](https://phabricator.services.mozilla.com/D287561) | — | — | — | — | — | — | — |
| 322 | [D287605](https://phabricator.services.mozilla.com/D287605) | padenot | 2026-03-13 15:30:33 UTC | — | 2026-03-13 17:32:16 UTC by **jolin** (accept) | — | 2026-03-13 17:32:16 UTC by **jolin** | — |
| 323 | [D287606](https://phabricator.services.mozilla.com/D287606) | padenot | 2026-03-13 15:32:10 UTC | — | 2026-03-16 17:40:49 UTC by **alwu** (accept) | — | 2026-03-16 17:40:49 UTC by **alwu** | — |
| 324 | [D287617](https://phabricator.services.mozilla.com/D287617) | jari | 2026-03-13 16:30:16 UTC | — | 2026-03-13 17:01:45 UTC by **padenot** (accept) | — | 2026-03-13 17:01:45 UTC by **padenot** | — |
| 325 | [D287628](https://phabricator.services.mozilla.com/D287628) | alwu | 2026-03-13 17:50:27 UTC | 2026-03-16 19:37:26 UTC | 2026-03-17 12:58:39 UTC by **padenot** (accept) | 17.4 h | 2026-03-17 12:58:39 UTC by **padenot** | 17.4 h |
| 326 | [D287629](https://phabricator.services.mozilla.com/D287629) | alwu | 2026-03-13 17:50:34 UTC | 2026-03-16 19:39:00 UTC | 2026-03-17 12:58:35 UTC by **padenot** (accept) | 17.3 h | 2026-03-17 12:58:35 UTC by **padenot** | 17.3 h |
| 327 | [D287630](https://phabricator.services.mozilla.com/D287630) | alwu | 2026-03-13 17:50:40 UTC | 2026-03-16 19:39:11 UTC | 2026-03-17 12:58:22 UTC by **padenot** (accept) | 17.3 h | 2026-03-17 12:58:22 UTC by **padenot** | 17.3 h |
| 328 | [D287631](https://phabricator.services.mozilla.com/D287631) | alwu | 2026-03-13 17:50:46 UTC | 2026-03-16 19:39:52 UTC | 2026-03-17 12:45:37 UTC by **padenot** (accept) | 17.1 h | 2026-03-17 12:45:37 UTC by **padenot** | 17.1 h |
| 329 | [D287632](https://phabricator.services.mozilla.com/D287632) | alwu | 2026-03-13 17:50:52 UTC | 2026-03-16 19:41:02 UTC | 2026-03-17 12:58:14 UTC by **padenot** (accept) | 17.3 h | 2026-03-17 12:58:14 UTC by **padenot** | 17.3 h |
| 330 | [D287633](https://phabricator.services.mozilla.com/D287633) | alwu | 2026-03-13 17:51:00 UTC | 2026-03-16 19:41:45 UTC | 2026-03-17 12:58:06 UTC by **padenot** (accept) | 17.3 h | 2026-03-17 12:58:06 UTC by **padenot** | 17.3 h |
| 331 | [D287634](https://phabricator.services.mozilla.com/D287634) | alwu | 2026-03-13 17:51:05 UTC | 2026-03-16 19:41:55 UTC | 2026-03-17 12:57:58 UTC by **padenot** (accept) | 17.3 h | 2026-03-17 12:57:58 UTC by **padenot** | 17.3 h |
| 332 | [D287655](https://phabricator.services.mozilla.com/D287655) | aosmond | 2026-03-13 18:44:44 UTC | 2026-03-13 18:47:14 UTC | 2026-03-16 13:31:06 UTC by **padenot** (accept) | 2.78 d | 2026-03-16 13:31:06 UTC by **padenot** | 2.78 d |
| 333 | [D287656](https://phabricator.services.mozilla.com/D287656) | aosmond | 2026-03-13 18:45:13 UTC | 2026-03-13 18:47:22 UTC | 2026-03-18 22:34:28 UTC by **jolin** (accept) | 5.16 d | 2026-03-18 22:34:28 UTC by **jolin** | 5.16 d |
| 334 | [D287669](https://phabricator.services.mozilla.com/D287669) | — | — | — | — | — | — | — |
| 335 | [D287670](https://phabricator.services.mozilla.com/D287670) | — | — | — | — | — | — | — |
| 336 | [D287730](https://phabricator.services.mozilla.com/D287730) | kinetik | 2026-03-13 21:55:31 UTC | — | 2026-03-16 14:51:03 UTC by **padenot** (accept) | — | 2026-03-16 14:51:03 UTC by **padenot** | — |
| 337 | [D287749](https://phabricator.services.mozilla.com/D287749) | RyanVM | 2026-03-13 23:39:08 UTC | 2026-03-13 23:39:56 UTC | 2026-03-16 13:33:07 UTC by **padenot** (accept) | 2.58 d | 2026-03-16 13:33:07 UTC by **padenot** | 2.58 d |
| 338 | [D287843](https://phabricator.services.mozilla.com/D287843) | sylvestre | 2026-03-15 22:56:15 UTC | — | 2026-03-16 17:08:31 UTC by **padenot** (accept) | — | 2026-03-16 17:08:31 UTC by **padenot** | — |
| 339 | [D287941](https://phabricator.services.mozilla.com/D287941) | sergesanspaille | 2026-03-16 11:29:00 UTC | — | 2026-03-16 14:59:45 UTC by **padenot** (accept) | — | 2026-03-16 14:59:45 UTC by **padenot** | — |
| 340 | [D287961](https://phabricator.services.mozilla.com/D287961) | padenot | 2026-03-16 13:04:50 UTC | — | — | — | — | — |
| 341 | [D288007](https://phabricator.services.mozilla.com/D288007) | — | — | — | — | — | — | — |
| 342 | [D288048](https://phabricator.services.mozilla.com/D288048) | — | — | — | — | — | — | — |
| 343 | [D288060](https://phabricator.services.mozilla.com/D288060) | alwu | 2026-03-16 19:36:50 UTC | 2026-03-16 19:36:56 UTC | 2026-03-17 13:02:43 UTC by **padenot** (accept) | 17.4 h | 2026-03-17 13:02:43 UTC by **padenot** | 17.4 h |
| 344 | [D288177](https://phabricator.services.mozilla.com/D288177) | anba | 2026-03-17 13:51:31 UTC | 2026-03-17 13:51:47 UTC | 2026-03-17 15:15:34 UTC by **padenot** (accept) | 1.4 h | 2026-03-17 15:15:34 UTC by **padenot** | 1.4 h |
| 345 | [D288178](https://phabricator.services.mozilla.com/D288178) | padenot | 2026-03-17 13:51:53 UTC | — | 2026-03-17 22:13:23 UTC by **alwu** (accept) | — | 2026-03-17 22:13:23 UTC by **alwu** | — |
| 346 | [D288179](https://phabricator.services.mozilla.com/D288179) | anba | 2026-03-17 13:51:59 UTC | 2026-03-17 13:52:18 UTC | 2026-03-17 15:21:42 UTC by **padenot** (accept) | 1.5 h | 2026-03-17 15:21:42 UTC by **padenot** | 1.5 h |
| 347 | [D288272](https://phabricator.services.mozilla.com/D288272) | — | — | — | — | — | — | — |
| 348 | [D288325](https://phabricator.services.mozilla.com/D288325) | — | — | — | — | — | — | — |
| 349 | [D288508](https://phabricator.services.mozilla.com/D288508) | jolin | 2026-03-18 19:46:26 UTC | 2026-03-18 19:48:34 UTC | 2026-03-18 20:06:23 UTC by **alwu** (accept) | 0.3 h | 2026-03-18 20:06:23 UTC by **alwu** | 0.3 h |
| 350 | [D288533](https://phabricator.services.mozilla.com/D288533) | — | — | — | — | — | — | — |
| 351 | [D288577](https://phabricator.services.mozilla.com/D288577) | tboiko | 2026-03-19 02:45:08 UTC | — | — | — | — | — |
| 352 | [D288601](https://phabricator.services.mozilla.com/D288601) | — | — | — | — | — | — | — |
| 353 | [D288634](https://phabricator.services.mozilla.com/D288634) | jmoss | 2026-03-19 12:50:07 UTC | — | 2026-03-19 13:47:42 UTC by **padenot** (accept) | — | 2026-03-19 13:47:42 UTC by **padenot** | — |
| 354 | [D288636](https://phabricator.services.mozilla.com/D288636) | mtlynch | 2026-03-19 13:06:30 UTC | — | 2026-03-19 14:05:02 UTC by **padenot** (accept) | — | 2026-03-19 14:05:02 UTC by **padenot** | — |
| 355 | [D288803](https://phabricator.services.mozilla.com/D288803) | — | — | — | — | — | — | — |
| 356 | [D288804](https://phabricator.services.mozilla.com/D288804) | — | — | — | — | — | — | — |
| 357 | [D288806](https://phabricator.services.mozilla.com/D288806) | alwu | 2026-03-20 00:36:20 UTC | 2026-03-20 00:39:26 UTC | 2026-03-20 01:10:25 UTC by **jolin** (accept) | 0.5 h | 2026-03-20 01:10:25 UTC by **jolin** | 0.5 h |
| 358 | [D288812](https://phabricator.services.mozilla.com/D288812) | — | — | — | — | — | — | — |
| 359 | [D288942](https://phabricator.services.mozilla.com/D288942) | — | — | — | — | — | — | — |
| 360 | [D288957](https://phabricator.services.mozilla.com/D288957) | — | — | — | — | — | — | — |
| 361 | [D288962](https://phabricator.services.mozilla.com/D288962) | — | — | — | — | — | — | — |
| 362 | [D288963](https://phabricator.services.mozilla.com/D288963) | — | — | — | — | — | — | — |
| 363 | [D289047](https://phabricator.services.mozilla.com/D289047) | jolin | 2026-03-21 06:59:54 UTC | 2026-03-21 07:00:06 UTC | 2026-03-25 21:26:01 UTC by **alwu** (accept) | 4.60 d | 2026-03-25 21:26:01 UTC by **alwu** | 4.60 d |
| 364 | [D289049](https://phabricator.services.mozilla.com/D289049) | emilio | 2026-03-21 09:51:00 UTC | — | — | — | — | — |
| 365 | [D289105](https://phabricator.services.mozilla.com/D289105) | — | — | — | 2026-03-30 12:05:31 UTC by **padenot** (accept) | — | 2026-03-30 12:05:31 UTC by **padenot** | — |
| 366 | [D289172](https://phabricator.services.mozilla.com/D289172) | sergesanspaille | 2026-03-23 11:15:34 UTC | 2026-03-23 11:16:52 UTC | 2026-03-25 21:26:58 UTC by **alwu** (accept) | 2.42 d | 2026-03-25 21:26:58 UTC by **alwu** | 2.42 d |
| 367 | [D289190](https://phabricator.services.mozilla.com/D289190) | — | — | — | — | — | — | — |
| 368 | [D289272](https://phabricator.services.mozilla.com/D289272) | ng | 2026-03-23 17:20:59 UTC | — | — | — | — | — |
| 369 | [D289330](https://phabricator.services.mozilla.com/D289330) | — | — | — | — | — | — | — |
| 370 | [D289335](https://phabricator.services.mozilla.com/D289335) | mccr8 | 2026-03-23 19:57:41 UTC | — | 2026-03-23 20:06:28 UTC by **kinetik** (accept) | — | 2026-03-23 20:06:28 UTC by **kinetik** | — |
| 371 | [D289353](https://phabricator.services.mozilla.com/D289353) | — | — | — | — | — | — | — |
| 372 | [D289360](https://phabricator.services.mozilla.com/D289360) | — | — | — | — | — | — | — |
| 373 | [D289369](https://phabricator.services.mozilla.com/D289369) | — | — | — | — | — | — | — |
| 374 | [D289377](https://phabricator.services.mozilla.com/D289377) | — | — | — | — | — | — | — |
| 375 | [D289379](https://phabricator.services.mozilla.com/D289379) | — | — | — | — | — | — | — |
| 376 | [D289383](https://phabricator.services.mozilla.com/D289383) | — | — | — | — | — | — | — |
| 377 | [D289394](https://phabricator.services.mozilla.com/D289394) | — | — | — | — | — | — | — |
| 378 | [D289397](https://phabricator.services.mozilla.com/D289397) | — | — | — | — | — | — | — |
| 379 | [D289402](https://phabricator.services.mozilla.com/D289402) | — | — | — | — | — | — | — |
| 380 | [D289406](https://phabricator.services.mozilla.com/D289406) | — | — | — | — | — | — | — |
| 381 | [D289415](https://phabricator.services.mozilla.com/D289415) | — | — | — | — | — | — | — |
| 382 | [D289416](https://phabricator.services.mozilla.com/D289416) | — | — | — | — | — | — | — |
| 383 | [D289432](https://phabricator.services.mozilla.com/D289432) | — | — | — | — | — | — | — |
| 384 | [D289598](https://phabricator.services.mozilla.com/D289598) | — | — | — | — | — | — | — |
| 385 | [D289622](https://phabricator.services.mozilla.com/D289622) | sergesanspaille | 2026-03-24 17:48:16 UTC | 2026-03-24 17:48:31 UTC | 2026-03-25 14:12:51 UTC by **padenot** (accept) | 20.4 h | 2026-03-25 14:12:51 UTC by **padenot** | 20.4 h |
| 386 | [D289623](https://phabricator.services.mozilla.com/D289623) | sergesanspaille | 2026-03-24 17:48:22 UTC | 2026-03-24 17:48:38 UTC | 2026-03-25 14:12:27 UTC by **padenot** (accept) | 20.4 h | 2026-03-25 14:12:27 UTC by **padenot** | 20.4 h |
| 387 | [D289641](https://phabricator.services.mozilla.com/D289641) | — | — | — | — | — | — | — |
| 388 | [D289646](https://phabricator.services.mozilla.com/D289646) | — | — | — | — | — | — | — |
| 389 | [D289647](https://phabricator.services.mozilla.com/D289647) | — | — | — | — | — | — | — |
| 390 | [D289656](https://phabricator.services.mozilla.com/D289656) | — | — | — | — | — | — | — |
| 391 | [D289669](https://phabricator.services.mozilla.com/D289669) | — | — | — | — | — | — | — |
| 392 | [D289679](https://phabricator.services.mozilla.com/D289679) | — | — | — | — | — | — | — |
| 393 | [D289710](https://phabricator.services.mozilla.com/D289710) | — | — | — | — | — | — | — |
| 394 | [D289711](https://phabricator.services.mozilla.com/D289711) | — | — | — | — | — | — | — |
| 395 | [D289842](https://phabricator.services.mozilla.com/D289842) | — | — | — | — | — | — | — |
| 396 | [D289873](https://phabricator.services.mozilla.com/D289873) | — | — | — | — | — | — | — |
| 397 | [D289977](https://phabricator.services.mozilla.com/D289977) | — | — | — | — | — | — | — |
| 398 | [D290045](https://phabricator.services.mozilla.com/D290045) | sergesanspaille | 2026-03-26 08:50:55 UTC | — | — | — | — | — |
| 399 | [D290201](https://phabricator.services.mozilla.com/D290201) | — | — | — | — | — | — | — |
| 400 | [D290544](https://phabricator.services.mozilla.com/D290544) | — | — | — | — | — | — | — |
| 401 | [D290588](https://phabricator.services.mozilla.com/D290588) | — | — | — | — | — | — | — |
| 402 | [D290615](https://phabricator.services.mozilla.com/D290615) | — | — | — | — | — | — | — |
| 403 | [D290663](https://phabricator.services.mozilla.com/D290663) | — | — | — | — | — | — | — |
| 404 | [D290697](https://phabricator.services.mozilla.com/D290697) | — | — | — | — | — | — | — |
| 405 | [D290698](https://phabricator.services.mozilla.com/D290698) | — | — | — | — | — | — | — |
| 406 | [D290699](https://phabricator.services.mozilla.com/D290699) | emilio | 2026-03-28 14:15:08 UTC | — | 2026-04-01 18:24:58 UTC by **alwu** (comment) | — | — | — |
| 407 | [D290700](https://phabricator.services.mozilla.com/D290700) | — | — | — | — | — | — | — |
| 408 | [D290701](https://phabricator.services.mozilla.com/D290701) | — | — | — | — | — | — | — |
| 409 | [D290715](https://phabricator.services.mozilla.com/D290715) | — | — | — | — | — | — | — |
| 410 | [D290716](https://phabricator.services.mozilla.com/D290716) | — | — | — | — | — | — | — |
| 411 | [D290717](https://phabricator.services.mozilla.com/D290717) | — | — | — | — | — | — | — |
| 412 | [D290718](https://phabricator.services.mozilla.com/D290718) | — | — | — | — | — | — | — |
| 413 | [D290731](https://phabricator.services.mozilla.com/D290731) | — | — | 2026-03-31 23:59:16 UTC | 2026-04-01 18:34:03 UTC by **alwu** (accept) | 18.6 h | 2026-04-01 18:34:03 UTC by **alwu** | 18.6 h |
| 414 | [D290769](https://phabricator.services.mozilla.com/D290769) | — | — | — | — | — | — | — |
| 415 | [D290780](https://phabricator.services.mozilla.com/D290780) | — | — | — | — | — | — | — |
| 416 | [D290863](https://phabricator.services.mozilla.com/D290863) | — | — | — | — | — | — | — |
| 417 | [D290891](https://phabricator.services.mozilla.com/D290891) | padenot | 2026-03-30 13:52:18 UTC | — | 2026-03-31 19:40:26 UTC by **alwu** (accept) | — | 2026-03-31 19:40:26 UTC by **alwu** | — |
| 418 | [D290940](https://phabricator.services.mozilla.com/D290940) | — | — | — | — | — | — | — |
| 419 | [D290958](https://phabricator.services.mozilla.com/D290958) | — | — | — | — | — | — | — |
| 420 | [D290978](https://phabricator.services.mozilla.com/D290978) | — | — | — | — | — | — | — |
| 421 | [D290981](https://phabricator.services.mozilla.com/D290981) | — | — | — | — | — | — | — |
| 422 | [D291017](https://phabricator.services.mozilla.com/D291017) | — | — | — | — | — | — | — |
| 423 | [D291050](https://phabricator.services.mozilla.com/D291050) | — | — | — | — | — | — | — |
| 424 | [D291419](https://phabricator.services.mozilla.com/D291419) | — | — | — | — | — | — | — |
| 425 | [D291435](https://phabricator.services.mozilla.com/D291435) | — | — | — | — | — | — | — |
| 426 | [D291535](https://phabricator.services.mozilla.com/D291535) | — | — | — | — | — | — | — |
| 427 | [D291541](https://phabricator.services.mozilla.com/D291541) | — | — | — | — | — | — | — |
| 428 | [D291850](https://phabricator.services.mozilla.com/D291850) | — | — | — | — | — | — | — |
| 429 | [D291885](https://phabricator.services.mozilla.com/D291885) | — | — | — | — | — | — | — |
| 430 | [D292320](https://phabricator.services.mozilla.com/D292320) | — | — | — | — | — | — | — |
| 431 | [D292321](https://phabricator.services.mozilla.com/D292321) | — | — | — | — | — | — | — |
| 432 | [D292328](https://phabricator.services.mozilla.com/D292328) | — | — | — | — | — | — | — |
| 433 | [D292411](https://phabricator.services.mozilla.com/D292411) | padenot | 2026-04-07 12:57:47 UTC | — | — | — | — | — |
| 434 | [D292482](https://phabricator.services.mozilla.com/D292482) | — | — | — | — | — | — | — |
| 435 | [D292501](https://phabricator.services.mozilla.com/D292501) | — | — | — | — | — | — | — |
| 436 | [D292516](https://phabricator.services.mozilla.com/D292516) | — | — | — | — | — | — | — |
| 437 | [D292534](https://phabricator.services.mozilla.com/D292534) | — | — | 2026-04-07 20:39:06 UTC | 2026-04-08 21:30:10 UTC by **alwu** (comment) | 1.04 d | 2026-04-10 12:10:27 UTC by **padenot** | 2.65 d |
| 438 | [D292537](https://phabricator.services.mozilla.com/D292537) | — | — | — | 2026-04-08 12:23:34 UTC by **padenot** (accept) | — | 2026-04-08 12:23:34 UTC by **padenot** | — |
| 439 | [D292546](https://phabricator.services.mozilla.com/D292546) | alwu | 2026-04-07 19:21:01 UTC | 2026-04-07 19:23:07 UTC | 2026-04-08 12:47:16 UTC by **padenot** (accept) | 17.4 h | 2026-04-08 12:47:16 UTC by **padenot** | 17.4 h |
| 440 | [D292577](https://phabricator.services.mozilla.com/D292577) | alwu | 2026-04-07 20:26:55 UTC | 2026-04-08 21:30:26 UTC | 2026-04-10 12:11:01 UTC by **padenot** (accept) | 1.61 d | 2026-04-10 12:11:01 UTC by **padenot** | 1.61 d |
| 441 | [D292697](https://phabricator.services.mozilla.com/D292697) | sergesanspaille | 2026-04-08 06:57:39 UTC | — | — | — | — | — |
| 442 | [D292771](https://phabricator.services.mozilla.com/D292771) | — | — | — | — | — | — | — |
| 443 | [D292922](https://phabricator.services.mozilla.com/D292922) | — | — | — | — | — | — | — |
| 444 | [D292947](https://phabricator.services.mozilla.com/D292947) | — | — | — | — | — | — | — |
| 445 | [D292978](https://phabricator.services.mozilla.com/D292978) | azebrowski | 2026-04-09 00:07:53 UTC | — | 2026-04-09 15:10:14 UTC by **padenot** (accept) | — | 2026-04-09 15:10:14 UTC by **padenot** | — |
| 446 | [D292979](https://phabricator.services.mozilla.com/D292979) | azebrowski | 2026-04-09 00:07:58 UTC | — | 2026-04-09 15:10:02 UTC by **padenot** (accept) | — | 2026-04-09 15:10:02 UTC by **padenot** | — |
| 447 | [D293039](https://phabricator.services.mozilla.com/D293039) | — | — | — | — | — | — | — |
| 448 | [D293320](https://phabricator.services.mozilla.com/D293320) | alwu | 2026-04-09 18:19:16 UTC | 2026-04-09 18:22:40 UTC | 2026-04-10 12:11:10 UTC by **padenot** (accept) | 17.8 h | 2026-04-10 12:11:10 UTC by **padenot** | 17.8 h |
| 449 | [D293325](https://phabricator.services.mozilla.com/D293325) | — | — | — | — | — | — | — |
| 450 | [D293346](https://phabricator.services.mozilla.com/D293346) | — | — | 2026-04-09 22:06:40 UTC | 2026-04-14 11:39:44 UTC by **padenot** (accept) | 4.56 d | 2026-04-14 11:39:44 UTC by **padenot** | 4.56 d |
| 451 | [D293434](https://phabricator.services.mozilla.com/D293434) | alwu | 2026-04-10 04:47:04 UTC | 2026-04-13 19:49:35 UTC | 2026-04-14 01:40:11 UTC by **jolin** (accept) | 5.8 h | 2026-04-14 01:40:11 UTC by **jolin** | 5.8 h |
| 452 | [D293435](https://phabricator.services.mozilla.com/D293435) | alwu | 2026-04-10 04:47:07 UTC | 2026-04-13 19:49:44 UTC | 2026-04-14 01:41:51 UTC by **jolin** (accept) | 5.9 h | 2026-04-14 01:41:51 UTC by **jolin** | 5.9 h |
| 453 | [D293436](https://phabricator.services.mozilla.com/D293436) | alwu | 2026-04-10 04:47:10 UTC | 2026-04-13 19:49:57 UTC | 2026-04-14 01:52:08 UTC by **jolin** (accept) | 6.0 h | 2026-04-14 01:52:08 UTC by **jolin** | 6.0 h |
| 454 | [D293576](https://phabricator.services.mozilla.com/D293576) | — | — | — | — | — | — | — |
| 455 | [D293578](https://phabricator.services.mozilla.com/D293578) | — | — | — | — | — | — | — |
| 456 | [D293635](https://phabricator.services.mozilla.com/D293635) | — | — | — | — | — | — | — |
| 457 | [D293708](https://phabricator.services.mozilla.com/D293708) | jolin | 2026-04-11 23:05:04 UTC | 2026-04-11 23:05:14 UTC | 2026-04-13 20:58:19 UTC by **alwu** (accept) | 1.91 d | 2026-04-13 20:58:19 UTC by **alwu** | 1.91 d |
| 458 | [D293808](https://phabricator.services.mozilla.com/D293808) | — | — | — | — | — | — | — |
| 459 | [D293825](https://phabricator.services.mozilla.com/D293825) | — | — | — | — | — | — | — |
| 460 | [D293826](https://phabricator.services.mozilla.com/D293826) | — | — | — | — | — | — | — |
| 461 | [D293827](https://phabricator.services.mozilla.com/D293827) | — | — | — | — | — | — | — |
| 462 | [D293906](https://phabricator.services.mozilla.com/D293906) | — | — | — | — | — | — | — |
| 463 | [D294021](https://phabricator.services.mozilla.com/D294021) | pehrsons | 2026-04-13 21:47:30 UTC | 2026-04-13 21:47:36 UTC | 2026-04-13 21:59:29 UTC by **aosmond** (accept) | 0.2 h | 2026-04-13 21:59:29 UTC by **aosmond** | 0.2 h |
| 464 | [D294027](https://phabricator.services.mozilla.com/D294027) | — | — | — | — | — | — | — |
| 465 | [D294108](https://phabricator.services.mozilla.com/D294108) | — | — | — | — | — | — | — |
| 466 | [D294130](https://phabricator.services.mozilla.com/D294130) | RyanVM | 2026-04-14 12:09:13 UTC | — | 2026-04-14 21:45:32 UTC by **alwu** (request-changes) | — | 2026-04-21 20:04:20 UTC by **alwu** | — |
| 467 | [D294131](https://phabricator.services.mozilla.com/D294131) | RyanVM | 2026-04-14 12:09:16 UTC | — | 2026-04-14 21:46:39 UTC by **alwu** (accept) | — | 2026-04-14 21:46:39 UTC by **alwu** | — |
| 468 | [D294132](https://phabricator.services.mozilla.com/D294132) | RyanVM | 2026-04-14 12:09:21 UTC | — | 2026-04-14 21:50:03 UTC by **alwu** (request-changes) | — | 2026-04-15 17:58:25 UTC by **alwu** | — |
| 469 | [D294152](https://phabricator.services.mozilla.com/D294152) | pehrsons | 2026-04-14 13:18:22 UTC | — | 2026-04-14 13:19:44 UTC by **padenot** (accept) | — | 2026-04-14 13:19:44 UTC by **padenot** | — |
| 470 | [D294203](https://phabricator.services.mozilla.com/D294203) | pehrsons | 2026-04-14 15:50:10 UTC | 2026-04-14 15:50:19 UTC | 2026-04-14 15:54:28 UTC by **padenot** (accept) | 0.1 h | 2026-04-14 15:54:28 UTC by **padenot** | 0.1 h |
| 471 | [D294218](https://phabricator.services.mozilla.com/D294218) | — | — | — | — | — | — | — |
| 472 | [D294303](https://phabricator.services.mozilla.com/D294303) | alwu | 2026-04-14 22:01:50 UTC | 2026-04-14 22:02:04 UTC | 2026-04-15 12:31:44 UTC by **padenot** (accept) | 14.5 h | 2026-04-15 12:31:44 UTC by **padenot** | 14.5 h |
| 473 | [D294380](https://phabricator.services.mozilla.com/D294380) | sfarre | 2026-04-15 09:56:06 UTC | 2026-04-15 09:57:52 UTC | 2026-04-21 20:06:33 UTC by **alwu** (accept) | 6.42 d | 2026-04-21 20:06:33 UTC by **alwu** | 6.42 d |
| 474 | [D294510](https://phabricator.services.mozilla.com/D294510) | emilio | 2026-04-15 20:59:39 UTC | — | 2026-04-15 21:14:35 UTC by **aosmond** (accept) | — | 2026-04-15 21:14:35 UTC by **aosmond** | — |
| 475 | [D294543](https://phabricator.services.mozilla.com/D294543) | — | — | — | — | — | — | — |
| 476 | [D294547](https://phabricator.services.mozilla.com/D294547) | — | — | — | — | — | — | — |
| 477 | [D294720](https://phabricator.services.mozilla.com/D294720) | RyanVM | 2026-04-16 17:50:07 UTC | — | 2026-04-17 20:56:24 UTC by **alwu** (accept) | — | 2026-04-17 20:56:24 UTC by **alwu** | — |
| 478 | [D294822](https://phabricator.services.mozilla.com/D294822) | — | — | — | — | — | — | — |
| 479 | [D294823](https://phabricator.services.mozilla.com/D294823) | — | — | — | — | — | — | — |
| 480 | [D294849](https://phabricator.services.mozilla.com/D294849) | alwu | 2026-04-17 01:57:56 UTC | 2026-04-17 01:58:06 UTC | 2026-04-18 08:16:55 UTC by **kinetik** (accept) | 1.26 d | 2026-04-18 08:16:55 UTC by **kinetik** | 1.26 d |
| 481 | [D294857](https://phabricator.services.mozilla.com/D294857) | RyanVM | 2026-04-17 03:05:13 UTC | — | 2026-04-21 19:30:02 UTC by **alwu** (accept) | — | 2026-04-21 19:30:02 UTC by **alwu** | — |
| 482 | [D294858](https://phabricator.services.mozilla.com/D294858) | RyanVM | 2026-04-17 03:05:17 UTC | — | 2026-04-21 19:38:57 UTC by **alwu** (accept) | — | 2026-04-21 19:38:57 UTC by **alwu** | — |
| 483 | [D294859](https://phabricator.services.mozilla.com/D294859) | RyanVM | 2026-04-17 03:05:22 UTC | — | 2026-04-21 19:46:14 UTC by **alwu** (accept) | — | 2026-04-21 19:46:14 UTC by **alwu** | — |
| 484 | [D294916](https://phabricator.services.mozilla.com/D294916) | tschuster | 2026-04-17 10:39:34 UTC | — | 2026-04-17 10:56:11 UTC by **padenot** (accept) | — | 2026-04-17 10:56:11 UTC by **padenot** | — |
| 485 | [D295075](https://phabricator.services.mozilla.com/D295075) | RyanVM | 2026-04-17 20:13:55 UTC | — | 2026-04-17 20:20:45 UTC by **alwu** (accept) | — | 2026-04-17 20:20:45 UTC by **alwu** | — |
| 486 | [D295100](https://phabricator.services.mozilla.com/D295100) | bwc | 2026-04-17 21:21:49 UTC | — | — | — | — | — |
| 487 | [D295291](https://phabricator.services.mozilla.com/D295291) | — | — | — | — | — | — | — |
| 488 | [D295325](https://phabricator.services.mozilla.com/D295325) | — | — | — | — | — | — | — |
| 489 | [D295341](https://phabricator.services.mozilla.com/D295341) | canaltinova | 2026-04-20 17:29:08 UTC | — | — | — | — | — |
| 490 | [D295365](https://phabricator.services.mozilla.com/D295365) | — | — | — | — | — | — | — |
| 491 | [D295485](https://phabricator.services.mozilla.com/D295485) | tschuster | 2026-04-21 10:07:03 UTC | 2026-04-21 10:07:13 UTC | 2026-04-21 11:20:13 UTC by **padenot** (accept) | 1.2 h | 2026-04-21 11:20:13 UTC by **padenot** | 1.2 h |
| 492 | [D295577](https://phabricator.services.mozilla.com/D295577) | sylvestre | 2026-04-21 15:37:16 UTC | — | 2026-04-21 16:05:41 UTC by **padenot** (accept) | — | 2026-04-21 16:05:41 UTC by **padenot** | — |
| 493 | [D295612](https://phabricator.services.mozilla.com/D295612) | — | — | — | — | — | — | — |
| 494 | [D295635](https://phabricator.services.mozilla.com/D295635) | alwu | 2026-04-21 18:47:55 UTC | 2026-04-21 18:48:10 UTC | 2026-04-21 20:02:32 UTC by **aosmond** (accept) | 1.2 h | 2026-04-21 20:02:32 UTC by **aosmond** | 1.2 h |
| 495 | [D295693](https://phabricator.services.mozilla.com/D295693) | alwu | 2026-04-21 20:58:37 UTC | 2026-04-21 20:58:47 UTC | 2026-04-22 00:42:06 UTC by **kinetik** (accept) | 3.7 h | 2026-04-22 00:42:06 UTC by **kinetik** | 3.7 h |
| 496 | [D295694](https://phabricator.services.mozilla.com/D295694) | alwu | 2026-04-21 20:58:41 UTC | 2026-04-21 20:58:55 UTC | 2026-04-22 01:19:44 UTC by **kinetik** (request-changes) | 4.3 h | 2026-04-22 21:24:18 UTC by **kinetik** | 1.02 d |
| 497 | [D295695](https://phabricator.services.mozilla.com/D295695) | alwu | 2026-04-21 20:58:45 UTC | 2026-04-21 21:01:05 UTC | 2026-04-21 23:31:11 UTC by **kinetik** (accept) | 2.5 h | 2026-04-21 23:31:11 UTC by **kinetik** | 2.5 h |
| 498 | [D295696](https://phabricator.services.mozilla.com/D295696) | alwu | 2026-04-21 20:58:49 UTC | 2026-04-21 21:01:09 UTC | 2026-04-22 21:33:42 UTC by **kinetik** (accept) | 1.02 d | 2026-04-22 21:33:42 UTC by **kinetik** | 1.02 d |
| 499 | [D295698](https://phabricator.services.mozilla.com/D295698) | alwu | 2026-04-21 20:59:15 UTC | 2026-04-21 21:01:17 UTC | 2026-04-22 00:24:07 UTC by **kinetik** (accept) | 3.4 h | 2026-04-22 00:24:07 UTC by **kinetik** | 3.4 h |
| 500 | [D295775](https://phabricator.services.mozilla.com/D295775) | — | — | — | — | — | — | — |
| 501 | [D295777](https://phabricator.services.mozilla.com/D295777) | — | — | 2026-04-22 09:16:25 UTC | 2026-04-23 14:57:21 UTC by **padenot** (accept) | 1.24 d | 2026-04-23 14:57:21 UTC by **padenot** | 1.24 d |
| 502 | [D295778](https://phabricator.services.mozilla.com/D295778) | — | — | — | — | — | — | — |
| 503 | [D295780](https://phabricator.services.mozilla.com/D295780) | — | — | — | — | — | — | — |
| 504 | [D295781](https://phabricator.services.mozilla.com/D295781) | — | — | — | — | — | — | — |
| 505 | [D295914](https://phabricator.services.mozilla.com/D295914) | — | — | — | — | — | — | — |
| 506 | [D295932](https://phabricator.services.mozilla.com/D295932) | pehrsons | 2026-04-22 20:18:13 UTC | — | — | — | — | — |
| 507 | [D295942](https://phabricator.services.mozilla.com/D295942) | kinetik | 2026-04-22 20:46:09 UTC | — | 2026-04-22 21:35:48 UTC by **alwu** (accept) | — | 2026-04-22 21:35:48 UTC by **alwu** | — |
| 508 | [D295994](https://phabricator.services.mozilla.com/D295994) | alwu | 2026-04-23 01:12:00 UTC | 2026-04-23 01:12:14 UTC | 2026-04-23 01:39:29 UTC by **kinetik** (accept) | 0.5 h | 2026-04-23 01:39:29 UTC by **kinetik** | 0.5 h |
| 509 | [D296083](https://phabricator.services.mozilla.com/D296083) | RyanVM | 2026-04-23 12:52:12 UTC | — | 2026-04-24 20:00:06 UTC by **alwu** (accept) | — | 2026-04-24 20:00:06 UTC by **alwu** | — |
| 510 | [D296084](https://phabricator.services.mozilla.com/D296084) | RyanVM | 2026-04-23 12:52:15 UTC | — | 2026-04-24 20:02:56 UTC by **alwu** (accept) | — | 2026-04-24 20:02:56 UTC by **alwu** | — |
| 511 | [D296085](https://phabricator.services.mozilla.com/D296085) | RyanVM | 2026-04-23 12:52:19 UTC | 2026-04-24 20:07:44 UTC | 2026-04-24 20:52:26 UTC by **aosmond** (accept) | 0.7 h | 2026-04-24 20:52:26 UTC by **aosmond** | 0.7 h |
| 512 | [D296171](https://phabricator.services.mozilla.com/D296171) | alwu | 2026-04-23 17:20:04 UTC | — | — | — | — | — |
| 513 | [D296202](https://phabricator.services.mozilla.com/D296202) | pehrsons | 2026-04-23 19:09:14 UTC | — | — | — | — | — |
| 514 | [D296426](https://phabricator.services.mozilla.com/D296426) | azebrowski | 2026-04-24 17:28:25 UTC | 2026-04-24 17:28:39 UTC | 2026-04-24 17:39:11 UTC by **aosmond** (accept) | 0.2 h | 2026-04-24 17:39:11 UTC by **aosmond** | 0.2 h |
| 515 | [D296448](https://phabricator.services.mozilla.com/D296448) | RyanVM | 2026-04-24 19:31:25 UTC | — | 2026-04-24 21:09:19 UTC by **alwu** (accept) | — | 2026-04-24 21:09:19 UTC by **alwu** | — |
| 516 | [D296598](https://phabricator.services.mozilla.com/D296598) | RyanVM | 2026-04-26 22:48:17 UTC | — | 2026-04-27 00:01:44 UTC by **aosmond** (accept) | — | 2026-04-27 00:01:44 UTC by **aosmond** | — |
| 517 | [D296673](https://phabricator.services.mozilla.com/D296673) | — | — | — | — | — | — | — |
| 518 | [D296727](https://phabricator.services.mozilla.com/D296727) | bhearsum | 2026-04-27 14:54:09 UTC | — | — | — | — | — |
| 519 | [D296941](https://phabricator.services.mozilla.com/D296941) | pehrsons | 2026-04-28 09:48:40 UTC | — | — | — | — | — |
| 520 | [D296942](https://phabricator.services.mozilla.com/D296942) | pehrsons | 2026-04-28 09:48:48 UTC | — | — | — | — | — |
| 521 | [D296943](https://phabricator.services.mozilla.com/D296943) | pehrsons | 2026-04-28 09:48:56 UTC | — | — | — | — | — |