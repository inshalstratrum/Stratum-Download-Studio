# Phase 2A.7A Website Compatibility Matrix

Audit date: 2026-07-12. Input contains **161** numbered entries. This is an engine-routing assessment, not a compatibility claim. No live URL was tested in Stratum during this phase; therefore every entry is **awaiting Stratum verification** or unsupported/not applicable.

## Reading the matrix

- Class/access: `S` source, `A` archive/aggregator/directory, `M` marketplace/service, `C` competitor/tool-like service, `DUP` duplicate/subset; `P` public, `L` login, `PAY` paid/subscription/paywall, `DRM` protected playback likely/material.
- Extractors: `Y:name` = named extractor observed in the official yt-dlp 2026.03.17 package used by this audit; `Gen` = only generic detection is plausible; `—` = no confident match. `G:name` = named match in official gallery-dl supported-site evidence. Extractor presence is **engine-supported, awaiting Stratum verification**, never a tested result. Upstream lists must be rechecked against the pinned target before implementation.
- Possibilities are `direct HTTP / generic media / image-gallery / video-audio / document-PDF`: `Y` plausible, `C` conditional on the page/authorization, `N` no/poor fit.
- Route: `YD` yt-dlp, `GD` gallery-dl, `HTTP` direct HTTP, `BC` browser-captured complete media, `PDF` direct download then optional Poppler processing, `AUTH` future governed authenticated support, `UN` unsupported, `NA` not applicable. A route list is ordered preference, not sequential invocation.
- Priority: `P0` release-foundation fixture, `P1` early compatibility, `P2` later/opportunistic, `P3` governed/low priority, `PX` protected/not applicable. `NT` means manual test not performed.

## Stock, open, education and mainstream social (1–56)

| # | Name / canonical domain | Class/access | Official extractor evidence | Possibilities D/G/I/V/PDF | Likely route and status | Pri | Required fixture / manual | Risks and limitations |
|---:|---|---|---|---|---|---:|---|---|
| 1 | Pexels — pexels.com | S/P | Y:Gen; G:Pexels | Y/C/Y/C/N | GD, HTTP; awaiting verification | P1 | Licensed image collection + video; NT | Licence/attribution, pagination |
| 2 | Pixabay — pixabay.com | S/P | Y:Gen; G:— | Y/C/Y/Y/N | HTTP, BC/YD generic; awaiting | P1 | Licensed image + MP4; NT | API/CDN changes, asset licence |
| 3 | Mixkit — mixkit.co | S/P | Y:Gen; G:— | Y/C/Y/Y/N | HTTP/BC; awaiting | P2 | Licensed clip page; NT | Terms, signed CDN |
| 4 | Videezy — videezy.com | S/P/L | Y:Gen; G:— | C/C/C/Y/N | HTTP/BC; awaiting | P2 | Free licensed clip; NT | Account/attribution variants |
| 5 | Videvo — videvo.net | S/P/L/PAY | Y:Gen; G:— | C/C/C/Y/N | HTTP/BC/AUTH; awaiting | P2 | Free authorized clip; NT | Subscription/licence |
| 6 | Coverr — coverr.co | S/P | Y:Gen; G:— | Y/C/Y/Y/N | HTTP/BC; awaiting | P2 | Licensed clip; NT | CDN and licence metadata |
| 7 | Mazwai — mazwai.com | S/P | Y:Gen; G:— | Y/C/C/Y/N | HTTP/BC; awaiting | P2 | Licensed clip; NT | Attribution terms |
| 8 | Dareful — dareful.com | S/P/L | Y:Gen; G:— | C/C/N/Y/N | HTTP/BC; awaiting | P3 | Authorized clip; NT | Registration/licence |
| 9 | Life of Vids — lifeofvids.com | S/P | Y:Gen; G:— | C/C/C/Y/N | HTTP/BC; awaiting | P3 | Licensed clip; NT | Site drift |
| 10 | Vidsplay — vidsplay.com | S/P | Y:Gen; G:— | C/C/N/Y/N | HTTP/BC; awaiting | P3 | Licensed clip; NT | Terms/redirects |
| 11 | SplitShire — splitshire.com | S/P | Y:Gen; G:— | C/C/Y/Y/N | HTTP/BC; awaiting | P3 | Licensed asset; NT | Mixed images/video |
| 12 | Free Nature Stock — freenaturestock.com | S/P | Y:Gen; G:— | Y/C/Y/Y/N | HTTP/BC; awaiting | P3 | Licensed asset; NT | Licence provenance |
| 13 | Motion Elements — motionelements.com | M/L/PAY | Y:Gen; G:— | C/C/C/C/N | AUTH/HTTP; awaiting | P3 | Purchased asset receipt; NT | Paywall/licence, no bypass |
| 14 | Freepik — freepik.com | M/P/L/PAY | Y:Gen; G:— | C/C/Y/C/N | AUTH/HTTP; awaiting | P3 | Owned free/premium asset; NT | Licensing/account limits |
| 15 | X Stock Video — domain uncertain | S? | Y:—; G:— | C/C/C/C/N | UN pending canonical identity | PX | Canonical URL first; NT | Ambiguous entity/domain |
| 16 | Stock Footage 4 Free — stockfootageforfree.com? | S/P/L | Y:Gen; G:— | C/C/N/Y/N | HTTP/BC; awaiting | P3 | Authorized clip; NT | Domain/status uncertainty |
| 17 | Ignite Motion — ignitemotion.com | S/P | Y:Gen; G:— | C/C/N/Y/N | HTTP/BC; awaiting | P3 | Licensed background; NT | Site availability |
| 18 | Beachfront B-Roll — beachfrontbroll.com? | S/P | Y:Gen; G:— | C/C/N/Y/N | HTTP/BC; awaiting | P3 | Licensed clip; NT | Canonical domain/status |
| 19 | Production Crate — productioncrate.com | M/P/L/PAY | Y:Gen; G:— | C/C/Y/Y/N | AUTH/HTTP; awaiting | P3 | Authorized free asset; NT | Quotas/licence |
| 20 | Footage Crate — footagecrate.com | DUP/M/L/PAY | Y:Gen; G:— | C/C/N/Y/N | Same ecosystem as #19; awaiting | P3 | Footage asset; NT | Duplicate brand/account |
| 21 | Clipstill — clipstill.com | M/P/PAY | Y:Gen; G:— | C/C/Y/Y/N | HTTP/AUTH; awaiting | P3 | Licensed cinemagraph; NT | Paywall/licence |
| 22 | CuteStockFootage — cutestockfootage.com | S/P | Y:Gen; G:— | C/C/Y/Y/N | HTTP/BC; awaiting | P3 | Licensed asset; NT | Site drift |
| 23 | World Clips — domain uncertain | S? | Y:—; G:— | C/C/C/C/N | UN pending identity | PX | Canonical URL first; NT | Ambiguous name |
| 24 | Internet Archive — archive.org | A/P/L | Y:archive.org; G:— | Y/Y/Y/Y/Y | YD/HTTP/PDF; engine-supported, awaiting | P0 | Public-domain item with MP4/PDF; NT | Item licences, large collections |
| 25 | Wikimedia Commons — commons.wikimedia.org | A/P | Y:wikimedia.org; G:Wikimedia | Y/Y/Y/Y/Y | YD/GD/HTTP/PDF; awaiting | P0 | CC image/video/PDF; NT | Attribution and derivatives |
| 26 | TED — ted.com | S/P | Y:TedTalk/Series/Playlist | C/Y/C/Y/N | YD; engine-supported, awaiting | P1 | Public talk + subtitles; NT | Embedded providers/terms |
| 27 | Khan Academy — khanacademy.org | S/P/L | Y:khanacademy | C/Y/C/Y/C | YD/HTTP; awaiting | P1 | Public lesson; NT | YouTube embeds/account areas |
| 28 | NASA Video — nasa.gov / images.nasa.gov | A/P | Y:Gen | Y/Y/Y/Y/Y | HTTP/BC/PDF; awaiting | P1 | Public NASA MP4/image/PDF; NT | Multiple hosts/usage marks |
| 29 | Library of Congress — loc.gov | A/P | Y:loc | Y/Y/Y/Y/Y | YD/HTTP/PDF; engine-supported, awaiting | P1 | Public item with rights note; NT | Per-item rights/large files |
| 30 | Prelinger Archives — archive.org/details/prelinger | DUP/A/P | Y:archive.org | Y/Y/Y/Y/Y | Same as #24; awaiting | P2 | Public-domain film; NT | Duplicate collection/rights |
| 31 | Moving Image Archive — archive.org/details/movies | DUP/A/P | Y:archive.org | Y/Y/Y/Y/Y | Same as #24; awaiting | P2 | Archive movie item; NT | Duplicate umbrella/size |
| 32 | MIT OpenCourseWare — ocw.mit.edu | S/P | Y:Gen | Y/C/C/Y/Y | HTTP/BC/PDF; awaiting | P1 | Course video + notes PDF; NT | Mixed hosts/licences |
| 33 | Coursera — coursera.org | M/L/PAY | Y:Gen | C/C/N/C/Y | AUTH; awaiting, no bypass | P3 | Enrolled free course asset; NT | Account/paywall/ToS |
| 34 | Open Culture — openculture.com | A/P | Y:Gen | C/C/C/C/Y | Follow source then route; awaiting | P3 | One linked public item; NT | Directory, third-party rights |
| 35 | National Geographic Video — nationalgeographic.com | S/L/PAY/DRM | Y:Gen | N/C/C/C/C | AUTH or UN protected | PX | Public trailer only; NT | Subscription/DRM/licence |
| 36 | C-SPAN — c-span.org | S/P | Y:CSpan | C/Y/N/Y/N | YD; engine-supported, awaiting | P1 | Public hearing clip; NT | Live/archive variants |
| 37 | YouTube — youtube.com | S/P/L | Y:youtube; G:— | C/Y/C/Y/N | YD canonical page; awaiting | P0 | Owned public video, split A/V/live; NT | Missing EJS/runtime, auth/DRM |
| 38 | Vimeo — vimeo.com | S/P/L/PAY | Y:vimeo family; G:— | C/Y/C/Y/N | YD canonical page; awaiting | P0 | Owned public/embed/private-authorized; NT | Password/auth, embeds |
| 39 | TikTok — tiktok.com | S/P/L | Y:TikTok family; G:TikTok | C/Y/Y/Y/N | YD/GD canonical page; awaiting | P0 | Owned public post/profile; NT | Current browser routing gap, cookies |
| 40 | Instagram — instagram.com | S/P/L | Y:Instagram family; G:Instagram | C/Y/Y/Y/N | YD/GD canonical page; awaiting | P0 | Owned public post/reel/carousel; NT | Routing gap, login/rate limits |
| 41 | Facebook Watch — facebook.com/watch | DUP/S/P/L | Y:facebook family; G:Facebook | C/Y/Y/Y/N | YD/GD canonical page; awaiting | P0 | Owned public video/reel; NT | Routing gap, cookies |
| 42 | Twitch — twitch.tv | S/P/L | Y:twitch family | C/Y/N/Y/N | YD; awaiting | P1 | Owned clip/VOD/live; NT | Live/chat/auth, expiring URLs |
| 43 | X — x.com / twitter.com | S/P/L | Y:twitter family; G:Twitter/Nitter | C/Y/Y/Y/N | YD/GD canonical post; awaiting | P0 | Owned public post with split A/V; NT | Current rendition-picker gap |
| 44 | Reddit — reddit.com | S/P/L | Y:Reddit; G:Reddit | C/Y/Y/Y/N | YD/GD canonical post; awaiting | P1 | Public self-hosted video/gallery; NT | NSFW/auth/external embeds |
| 45 | Dailymotion — dailymotion.com | S/P/L | Y:dailymotion family | C/Y/N/Y/N | YD; awaiting | P1 | Public owned video; NT | Ads/geo/login |
| 46 | LinkedIn — linkedin.com | S/L | Y:LinkedIn | C/C/C/Y/N | AUTH/YD later; awaiting | P3 | User-owned public post; NT | Login/privacy/ToS |
| 47 | Pinterest — pinterest.com | S/P/L | Y:Pinterest; G:Pinterest | C/Y/Y/Y/N | GD/YD canonical pin; awaiting | P0 | Owned pin/board/multi-player; NT | Current player ownership gap |
| 48 | Snapchat — snapchat.com | S/P/L | Y:SnapchatSpotlight | C/Y/C/Y/N | YD canonical page/BC; awaiting | P1 | Owned Spotlight/story; NT | Story auth, ownership/ext errors |
| 49 | Threads — threads.com / threads.net | S/P/L | Y:—; G:— | C/C/Y/Y/N | BC/HTTP then future canonical support | P1 | Owned public post + query URL; NT | No dedicated match, filename leak report |
| 50 | Rumble — rumble.com | S/P/L | Y:Rumble family | C/Y/N/Y/N | YD canonical page; awaiting | P0 | Owned public page/embed/multi-player; NT | Current page-recognition gap |
| 51 | BitChute — bitchute.com | S/P/L | Y:BitChute | C/Y/N/Y/N | YD; awaiting | P2 | Owned public video; NT | Site availability/content policy |
| 52 | Veoh — veoh.com | S/P/L | Y:Veoh | C/Y/N/Y/N | YD; awaiting | P2 | Authorized public video; NT | Legacy service/site drift |
| 53 | Metacafe — metacafe.com | S?/legacy | Y:— | N/N/N/N/N | UN/NA if defunct | PX | Confirm service status; NT | Legacy/defunct likelihood |
| 54 | Imgur — imgur.com | S/P/L | Y:Imgur; G:imgur | Y/Y/Y/Y/N | GD/YD/HTTP; awaiting | P1 | Public image/album/video; NT | Rate limits/NSFW |
| 55 | Gfycat — gfycat.com | S?/legacy | Y:— | N/N/N/N/N | UN/NA if defunct | PX | Confirm service status; NT | Defunct service |
| 56 | Tumblr — tumblr.com | S/P/L | Y:Tumblr; G:Tumblr | C/Y/Y/Y/N | GD/YD; awaiting | P1 | Owned public post/blog; NT | OAuth/cookies/adult policy |

## Entertainment, news, commercial and institutional sources (57–122)

| # | Name / canonical domain | Class/access | Official extractor evidence | Possibilities D/G/I/V/PDF | Likely route and status | Pri | Required fixture / manual | Risks and limitations |
|---:|---|---|---|---|---|---:|---|---|
| 57 | Tubi — tubitv.com | S/P/L/DRM | Y:tubitv | N/C/N/C/N | YD for unprotected only; otherwise UN | PX | Public trailer/unprotected item; NT | Ads, geo, DRM |
| 58 | Pluto TV — pluto.tv | S/P/L/DRM | Y:PlutoTV | N/C/N/C/N | YD for unprotected only; otherwise UN | PX | Public unprotected clip; NT | Live/ads/DRM/geo |
| 59 | Crackle — crackle.com | S/P/L/DRM | Y:Gen | N/C/N/C/N | UN unless proven unprotected | PX | Public trailer; NT | DRM/geo/ads |
| 60 | Popcornflix — popcornflix.com | S/P/DRM | Y:Gen | N/C/N/C/N | UN unless unprotected | PX | Public trailer; NT | DRM/geo/service drift |
| 61 | JioCinema / Hotstar — hotstar.com / jiocinema.com | S/L/PAY/DRM | Y:hotstar | N/C/N/C/N | YD unprotected metadata only; DRM UN | PX | Free unprotected promo; NT | Subscription/geo/DRM, conflated brands |
| 62 | ZEE5 — zee5.com | S/L/PAY/DRM | Y:Zee5 | N/C/N/C/N | YD unprotected only; DRM UN | PX | Free unprotected promo; NT | Login/geo/DRM |
| 63 | Fandango at Home — athome.fandango.com | S/L/PAY/DRM | Y:— | N/N/N/N/N | UN protected | PX | Public trailer only; NT | Purchase rights/DRM |
| 64 | Plex — plex.tv | S/P/L/DRM | Y:Gen | C/C/N/C/N | AUTH/BC for owned server media only | P3 | User-owned Plex share; NT | Server auth, free-streaming DRM |
| 65 | Kanopy — kanopy.com | S/L/PAY/DRM | Y:Gen | N/N/N/N/N | UN protected | PX | Public trailer; NT | Library entitlement/DRM |
| 66 | Hoopla — hoopladigital.com | S/L/PAY/DRM | Y:Gen | N/N/N/N/N | UN protected | PX | Public trailer; NT | Library entitlement/DRM |
| 67 | Filmzie — filmzie.com | S/P/L/DRM | Y:Gen | N/C/N/C/N | UN unless unprotected | PX | Public trailer; NT | Ads/DRM/geo |
| 68 | BBC Motion Gallery via Getty — gettyimages.com/bbcmotiongallery | DUP/M/L/PAY | Y:Gen | C/C/C/Y/N | AUTH/HTTP after licensed purchase | P3 | Purchased licensed preview/delivery; NT | Marketplace rights/watermarks |
| 69 | AP Archive — aparchive.com | A/M/L/PAY | Y:Gen | C/C/C/Y/N | AUTH/HTTP after licence | P3 | Licensed preview/delivery; NT | Editorial licensing/paywall |
| 70 | Reuters Connect — reutersconnect.com | A/M/L/PAY | Y:Gen | C/C/C/Y/N | AUTH/HTTP after licence | P3 | Licensed account asset; NT | Contract/API restrictions |
| 71 | CNN Collection — cnn.com/collection? | A/M/L/PAY | Y:Gen | C/C/C/Y/N | AUTH/HTTP after licence | P3 | Licensed archive asset; NT | Canonical service/rights |
| 72 | Al Jazeera English — aljazeera.com | S/P | Y:AlJazeera | C/Y/C/Y/C | YD/BC; engine-supported, awaiting | P0 | Public article Brightcove/HLS; NT | Master-child routing/manual pending |
| 73 | Deutsche Welle — dw.com | S/P | Y:dw | C/Y/C/Y/C | YD/HTTP; awaiting | P1 | Public article/video; NT | Multi-language embeds |
| 74 | Bloomberg Video — bloomberg.com | S/P/L/PAY | Y:Bloomberg | C/Y/C/Y/N | YD for public video; awaiting | P1 | Public video page; NT | Paywall/geo/ads |
| 75 | Euronews — euronews.com | S/P | Y:Gen | C/Y/C/Y/N | BC/YD generic; awaiting | P1 | Public article video; NT | Embed/provider drift |
| 76 | France 24 — france24.com | S/P | Y:Gen | C/Y/C/Y/N | BC/YD generic; awaiting | P1 | Public report/live; NT | Live/geo/embed |
| 77 | CBS News Archive — cbsnews.com | S/P | Y:cbsnews family | C/Y/C/Y/N | YD; awaiting | P1 | Public clip/live page; NT | Ads/live variants |
| 78 | NBC News Archives — nbcnews.com | S/P | Y:NBCNews | C/Y/C/Y/N | YD; awaiting | P1 | Public article video; NT | Provider/ads/geo |
| 79 | Sky News — news.sky.com | S/P | Y:sky:news | C/Y/C/Y/N | YD; awaiting | P1 | Public article/live; NT | Live/geo/embeds |
| 80 | CNBC Video — cnbc.com/video | S/P/L | Y:CNBCVideo | C/Y/C/Y/N | YD canonical page; baseline-recognized, awaiting | P0 | Public page + browser button; NT | Manual regression still needed |
| 81 | New York Times Video — nytimes.com/video | S/P/L/PAY | Y:NYTimes | C/Y/C/Y/N | YD public items/AUTH later | P2 | Public video page; NT | Paywall/cookies |
| 82 | Guardian Video — theguardian.com/video | S/P/L | Y:Gen (podcast-only named) | C/Y/C/Y/N | BC/YD generic; awaiting | P2 | Public video page; NT | No confident video extractor |
| 83 | PBS NewsHour — pbs.org/newshour | S/P | Y:pbs | C/Y/C/Y/N | YD; awaiting | P1 | Public segment; NT | Station/provider variation |
| 84 | NHK World-Japan — www3.nhk.or.jp/nhkworld | S/P/L | Y:NhkVod family | C/Y/C/Y/N | YD; awaiting | P2 | Public VOD; NT | Geo/expiry/live |
| 85 | Channel 4 News — channel4.com/news | S/P/L/DRM | Y:Gen | N/C/C/C/N | BC only if unprotected; DRM UN | PX | Public news clip; NT | Access control/DRM/geo |
| 86 | British Pathé — britishpathe.com | A/M/P/L/PAY | Y:Gen | C/C/C/Y/N | HTTP/BC for licensed/public preview | P2 | Public-domain/licensed item; NT | Rights/watermarks |
| 87 | CriticalPast — criticalpast.com | A/M/P/PAY | Y:Gen | C/C/C/Y/N | HTTP after licence; awaiting | P3 | Licensed sample/delivery; NT | Commercial rights/watermarks |
| 88 | Shutterstock Video — shutterstock.com | M/L/PAY | Y:Gen | C/C/Y/Y/N | AUTH/HTTP purchased delivery | P3 | Purchased asset; NT | Licensing/account/anti-bot |
| 89 | Getty Images Video — gettyimages.com | M/L/PAY | Y:Gen | C/C/Y/Y/N | AUTH/HTTP purchased delivery | P3 | Purchased asset; NT | Licensing/watermarks |
| 90 | Adobe Stock Video — stock.adobe.com | M/L/PAY | Y:Gen | C/C/Y/Y/N | AUTH/HTTP purchased delivery | P3 | Purchased asset; NT | Adobe auth/licensing |
| 91 | iStock Video — istockphoto.com | DUP/M/L/PAY | Y:Gen | C/C/Y/Y/N | AUTH/HTTP purchased delivery | P3 | Purchased asset; NT | Getty ecosystem/licensing |
| 92 | Pond5 — pond5.com | M/L/PAY | Y:Gen | C/C/Y/Y/N | AUTH/HTTP purchased delivery | P3 | Purchased asset; NT | Marketplace rights |
| 93 | Storyblocks — storyblocks.com | M/L/PAY | Y:Gen | C/C/Y/Y/N | AUTH/HTTP purchased delivery | P3 | Subscriber-authorized asset; NT | Subscription/quotas |
| 94 | Envato Elements — elements.envato.com | M/L/PAY | Y:Gen | C/C/Y/Y/Y | AUTH/HTTP purchased delivery | P3 | Licensed asset/template; NT | Subscription/item licence |
| 95 | Artgrid — artgrid.io | M/L/PAY | Y:Gen | C/C/N/Y/N | AUTH/HTTP purchased delivery | P3 | Subscriber-authorized clip; NT | Subscription/DRM-like controls |
| 96 | Filmsupply — filmsupply.com | M/L/PAY | Y:Gen | C/C/N/Y/N | AUTH/HTTP purchased delivery | P3 | Licensed asset; NT | High-value licensing |
| 97 | Dissolve — dissolve.com | M/L/PAY | Y:Gen | C/C/Y/Y/N | AUTH/HTTP purchased delivery | P3 | Licensed asset; NT | Watermarks/licensing |
| 98 | Canva Pro Video — canva.com | M/L/PAY | Y:Gen | N/C/Y/Y/Y | AUTH future/export only | P3 | User-owned Canva export; NT | App API/auth/licensing |
| 99 | Uppbeat — uppbeat.io | M/P/L/PAY | Y:Gen | C/C/Y/Y/N | AUTH/HTTP authorized asset | P3 | Licensed free/premium asset; NT | Account/licence |
| 100 | ESA Video — esa.int / esawebtv.esa.int | A/P | Y:Gen | Y/Y/Y/Y/Y | HTTP/BC/PDF; awaiting | P1 | Public ESA video/image/PDF; NT | Usage/credit requirements |
| 101 | NOAA Ocean Exploration — oceanexplorer.noaa.gov | A/P | Y:Gen | Y/Y/Y/Y/Y | HTTP/BC/PDF; awaiting | P1 | Public MP4/image/PDF; NT | Government rights exceptions |
| 102 | JoVE — jove.com | M/L/PAY | Y:Gen | C/C/C/C/Y | AUTH future; no bypass | P3 | Open-access article only; NT | Paywall/copyright |
| 103 | CERN Document Server — cds.cern.ch | A/P/L | Y:Gen | Y/C/Y/Y/Y | HTTP/PDF/BC; awaiting | P1 | Public record with PDF/video; NT | Metadata/licence per item |
| 104 | US National Archives Catalog — catalog.archives.gov | A/P | Y:Gen | Y/C/Y/Y/Y | HTTP/BC/PDF; awaiting | P1 | Public catalog AV/PDF item; NT | Rights notes/huge files |
| 105 | Smithsonian Channel / Video — smithsonianchannel.com | S/P/L/PAY/DRM | Y:Gen | N/C/C/C/C | UN protected; HTTP only public assets | PX | Public trailer/museum asset; NT | Conflates channel with institution |
| 106 | BioDigital — biodigital.com | M/L/PAY | Y:Gen | N/N/C/C/C | AUTH/export only | P3 | User-owned permitted export; NT | Interactive models/licensing |
| 107 | Academic Earth — academicearth.org | A/P | Y:Gen | C/C/C/C/Y | Follow canonical source; awaiting | P3 | Linked open lecture; NT | Directory, third-party rights |
| 108 | Olympic Channel — olympics.com | S/P/L/DRM | Y:Gen | N/C/C/C/N | UN if protected; BC unprotected only | PX | Public unprotected clip; NT | Rights/geo/DRM |
| 109 | Red Bull TV — redbull.com / redbull.tv | S/P/L | Y:RedBull family | C/Y/C/Y/N | YD; engine-supported, awaiting | P1 | Public video/VOD; NT | Geo/live/provider |
| 110 | UFC Free Fights — ufc.com | S/P/L/PAY/DRM | Y:UFCTV/UFCArabia | N/C/N/C/N | YD unprotected free only; DRM UN | PX | Official free clip; NT | Subscription/DRM/geo |
| 111 | World Surf League — worldsurfleague.com | S/P/L/PAY | Y:Gen | C/C/C/Y/N | BC/AUTH; awaiting | P3 | Public highlight; NT | Login/live/rights |
| 112 | Europeana — europeana.eu | A/P | Y:Gen | Y/C/Y/Y/Y | HTTP/PDF; source-dependent | P1 | Public-domain AV/image/PDF; NT | Aggregated rights/redirects |
| 113 | DVIDS — dvidshub.net | A/P | Y:Gen | Y/C/Y/Y/Y | HTTP/BC/PDF; awaiting | P1 | Public-domain video/image; NT | Per-item rights/metadata |
| 114 | Public Domain Review — publicdomainreview.org | A/P | Y:Gen | C/C/Y/Y/Y | Follow source/HTTP/PDF | P2 | One public-domain article asset; NT | Curator links external sources |
| 115 | Wellcome Collection — wellcomecollection.org | A/P | Y:Gen | Y/C/Y/Y/Y | HTTP/PDF/BC; awaiting | P1 | CC image/film/PDF; NT | Per-item rights/IIIF |
| 116 | UN Audiovisual Library — unmultimedia.org / media.un.org | A/P | Y:UnitedNationsWebTv | C/Y/Y/Y/Y | YD/HTTP/PDF; awaiting | P1 | Public speech/video/document; NT | UN usage terms/live |
| 117 | Folkstreams — folkstreams.net | A/P | Y:Gen | C/C/C/Y/Y | BC/HTTP; awaiting | P2 | Authorized documentary; NT | Film-specific copyright |
| 118 | National Film Board of Canada — nfb.ca | A/S/P/L | Y:nfb | C/Y/C/Y/N | YD; engine-supported, awaiting | P1 | Free public film; NT | Geo/licensing |
| 119 | Macaulay Library — macaulaylibrary.org | A/P/L | Y:Gen | C/C/Y/Y/N | HTTP/AUTH; awaiting | P2 | Public low-res research media; NT | Scientific-use/licensing/account |
| 120 | Spielberg Jewish Film Archive — jewishfilmarchive.org? | A/P | Y:Gen | C/C/C/Y/Y | HTTP/BC/PDF; awaiting | P2 | Public archive film; NT | Canonical host/rights |
| 121 | Open Video Project — open-video.org | A/P | Y:Gen | Y/C/C/Y/Y | HTTP/PDF; awaiting | P2 | Public MPEG item; NT | Legacy formats/site availability |
| 122 | BFI Free Collection — player.bfi.org.uk/free | A/S/P/L/DRM | Y:Gen | N/C/C/C/N | UN protected; unprotected BC only | PX | Public free title/trailer; NT | Geo/DRM/copyright |

## Authenticated, course, regional, live, cloud and protected targets (123–161)

| # | Name / canonical domain | Class/access | Official extractor evidence | Possibilities D/G/I/V/PDF | Likely route and status | Pri | Required fixture / manual | Risks and limitations |
|---:|---|---|---|---|---|---:|---|---|
| 123 | Patreon — patreon.com | S/L/PAY | Y:patreon; G:Patreon | C/C/Y/Y/C | AUTH then YD/GD; awaiting | P3 | Creator-owned paid test post; NT | Consent, cookies, embeds, paywall |
| 124 | OnlyFans / Fansly — onlyfans.com / fansly.com | S/L/PAY | Y:—; G:Fansly only | C/C/Y/Y/N | AUTH/GD for Fansly; OnlyFans unsupported | P3 | Creator-owned test accounts; NT | Sensitive data, age, ToS, paywall |
| 125 | Substack — substack.com | S/P/L/PAY | Y:Gen; G:— | C/C/Y/Y/Y | HTTP/BC public; AUTH later | P2 | Author-owned public/paid post; NT | Email/session/paywall, embeds |
| 126 | Gumroad — gumroad.com | M/L/PAY | Y:Gen; G:— | C/C/Y/Y/Y | AUTH/HTTP purchased delivery | P3 | Creator-owned product; NT | Purchase/licensing/expiring links |
| 127 | Locals by Rumble — locals.com | S/L/PAY | Y:Gen; G:— | C/C/Y/Y/N | AUTH future | P3 | Creator-owned test community; NT | Subscription/session |
| 128 | Ko-fi — ko-fi.com | S/P/L/PAY | Y:Gen; G:— | C/C/Y/Y/Y | HTTP public/AUTH later | P3 | Creator-owned post; NT | Tier/paywall/embeds |
| 129 | Udemy — udemy.com | M/L/PAY/DRM | Y:udemy | N/C/N/C/Y | AUTH metadata/unprotected only; DRM UN | PX | Instructor-owned free course; NT | DRM, course rights, many assets |
| 130 | Skillshare — skillshare.com | M/L/PAY/DRM | Y:— | N/N/N/N/N | UN protected | PX | Instructor-owned trailer; NT | Subscription/DRM |
| 131 | MasterClass — masterclass.com | M/L/PAY/DRM | Y:— | N/N/N/N/N | UN protected | PX | Public trailer only; NT | Subscription/DRM |
| 132 | Pluralsight — pluralsight.com | M/L/PAY/DRM | Y:pluralsight | N/C/N/C/Y | AUTH unprotected only; DRM UN | PX | Author-owned/free course; NT | Subscription/DRM/ToS |
| 133 | LinkedIn Learning — linkedin.com/learning | DUP/M/L/PAY/DRM | Y:linkedin:learning | N/C/N/C/Y | AUTH unprotected only; DRM UN | PX | Instructor-owned preview; NT | Subscription/DRM |
| 134 | Teachable / Thinkific — teachable.com / thinkific.com | M/L/PAY | Y:Gen | C/C/C/C/Y | AUTH future per tenant | P3 | Owner test course on each platform; NT | Tenant domains, sessions, paywalls |
| 135 | Crunchyroll — crunchyroll.com | S/L/PAY/DRM | Y:— observed | N/N/N/N/N | UN protected | PX | Public trailer only; NT | DRM/subscription/geo |
| 136 | Bilibili — bilibili.com | S/P/L/PAY | Y:BiliBili family; G:Bilibili limited | C/Y/Y/Y/N | YD/GD; awaiting | P1 | Owned/public video + livephoto; NT | Region/login/API/subtitles |
| 137 | Nico Nico Douga — nicovideo.jp | S/P/L/PAY | Y:niconico family | C/Y/C/Y/N | YD; awaiting | P2 | Public video/live; NT | Login/geo/comments |
| 138 | iQIYI — iq.com / iqiyi.com | S/P/L/PAY/DRM | Y:iqiyi | N/C/N/C/N | YD unprotected only; DRM UN | PX | Public unprotected trailer; NT | DRM/geo/login |
| 139 | Youku — youku.com | S/P/L/PAY/DRM | Y:youku | N/C/N/C/N | YD unprotected only; DRM UN | PX | Public unprotected clip; NT | DRM/geo/API |
| 140 | Rakuten Viki — viki.com | S/P/L/PAY/DRM | Y:— observed | N/C/N/C/N | UN unless unprotected generic | PX | Public trailer; NT | DRM/subscription/geo/subtitles |
| 141 | SoundCloud — soundcloud.com | S/P/L/PAY | Y:soundcloud family | C/Y/Y/Y/N | YD; engine-supported, awaiting | P0 | Creator-owned track/playlist/art; NT | Original vs stream, metadata rights |
| 142 | Bandcamp — bandcamp.com | M/S/P/L/PAY | Y:Bandcamp family | C/Y/Y/Y/N | YD/HTTP purchased delivery | P1 | Artist-owned track/album; NT | Purchase/licence/metadata |
| 143 | Mixcloud — mixcloud.com | S/P/L/PAY | Y:mixcloud family | C/Y/Y/Y/N | YD; awaiting | P1 | Creator-owned public mix; NT | Geo/subscription/music rights |
| 144 | Spotify — open.spotify.com | S/L/PAY/DRM | Y:— | N/N/C/N/N | UN protected; metadata/art only if authorized | PX | Creator-owned podcast page; NT | DRM/licensing, no stream ripping |
| 145 | Apple Podcasts Web — podcasts.apple.com | A/P | Y:ApplePodcasts | C/Y/Y/Y/N | YD/HTTP feed media; awaiting | P1 | Public podcast episode/feed; NT | External hosts/redirects/metadata |
| 146 | Kick — kick.com | S/P/L | Y:kick live/VOD/clips | C/Y/N/Y/N | YD; awaiting | P1 | Creator-owned clip/VOD/live; NT | Live/auth/expiring URLs |
| 147 | AfreecaTV / SOOP — sooplive.com | S/P/L/PAY | Y:soop family | C/Y/C/Y/N | YD; awaiting | P2 | Public VOD/live; NT | Renamed service/region/login |
| 148 | Trovo — trovo.live | S/P/L | Y:Trovo family | C/Y/N/Y/N | YD; awaiting | P2 | Creator-owned clip/VOD/live; NT | Live/auth/region |
| 149 | Bigo Live — bigo.tv | S/P/L | Y:Bigo | C/Y/N/Y/N | YD; awaiting | P2 | Creator-owned public live/replay; NT | Live, age/privacy, region |
| 150 | VK — vk.com | S/P/L | Y:vk family | C/Y/Y/Y/N | YD; awaiting | P1 | Owned public post/video; NT | Login/region/API |
| 151 | OK.ru — ok.ru | S/P/L | Y:Odnoklassniki | C/Y/Y/Y/N | YD; awaiting | P2 | Owned public video; NT | Login/region |
| 152 | Telegram Web — t.me / web.telegram.org | S/P/L | Y:telegram:embed | C/C/Y/Y/Y | YD public embed/HTTP; AUTH later | P2 | Owner public-channel post; NT | Private channels, sensitive data |
| 153 | Douyin — douyin.com | S/P/L | Y:Douyin | C/Y/Y/Y/N | YD; awaiting | P1 | Owned public post; NT | Region/API/login |
| 154 | Xiaohongshu / RED — xiaohongshu.com | S/P/L | Y:XiaoHongShu | C/Y/Y/Y/N | YD; awaiting | P1 | Owned public note/video/gallery; NT | Login/rate/region |
| 155 | Kwai / Kuaishou — kwai.com / kuaishou.com | S/P/L | Y:— observed | C/C/Y/Y/N | BC/HTTP; future extractor decision | P2 | Owned public post on each brand; NT | Distinct regions/APIs/login |
| 156 | Google Drive — drive.google.com | M/P/L | Y:GoogleDrive | Y/Y/N/Y/Y | YD/HTTP authorized share; awaiting | P1 | Owner public file/folder; NT | Quota/virus page/permissions |
| 157 | Dropbox — dropbox.com | M/P/L | Y:Dropbox | Y/Y/N/Y/Y | YD/HTTP authorized share; awaiting | P1 | Owner public shared file; NT | Redirects/permissions |
| 158 | MEGA — mega.nz | M/P/L | Y:— | C/N/N/C/Y | AUTH/future dedicated client, not BC | P3 | Owner public encrypted link; NT | Client-side encryption, keys, size |
| 159 | OneDrive / SharePoint — onedrive.live.com / sharepoint.com | M/P/L | Y:— | C/C/N/Y/Y | HTTP/AUTH authorized share | P2 | Owner public OneDrive + tenant SharePoint; NT | Tenant auth/redirects/permissions |
| 160 | Adult tube sites group — multiple domains | A-group/P/L | Y:PornHub/XVideos/XNXX named; G:varies | C/Y/C/Y/N | YD allowlisted domains only; awaiting | P3 | Lawful adult-owned test per named domain; NT | Age/consent/law/NSFW, group is not one site |
| 161 | Live cam sites group — multiple domains | A-group/P/L/PAY | Y:Chaturbate/Stripchat | C/Y/N/Y/N | YD public authorized streams only | P3 | Performer-owned/public test per domain; NT | Live recording consent, privacy, tokens |

## Summary and certification boundary

- Assessed: **161/161 numbered entries**. Newly verified compatible in Stratum: **0**. Manual tests performed in this phase: **0**.
- Strong initial fixture candidates are open/public sources and current named extractors: Internet Archive, Wikimedia, YouTube, Vimeo, major public social pages, Al Jazeera/Brightcove, CNBC, SoundCloud and representative direct image/PDF sources.
- Entries 15 and 23 lack a confidently identified canonical entity; they cannot receive an engine claim until a canonical URL is supplied. Several named “sites” are collections, duplicate brands, directories, marketplaces, or multi-domain groups.
- Subscription, purchased and authenticated entries require explicit user authority and the later consent-governance phase. A subscription is not permission to bypass access controls.
- DRM-protected entries remain unsupported. Stratum must accurately return protected/unsupported rather than downgrade to raw segments or claim generic compatibility.
- Certification requires an exact backend bundle, lawful owned/authorized fixture, expected route, clean automated result, FFprobe/signature validation as applicable, and a dated manual pass in Stratum. Until then the maximum label is **engine-supported, awaiting Stratum verification**.
