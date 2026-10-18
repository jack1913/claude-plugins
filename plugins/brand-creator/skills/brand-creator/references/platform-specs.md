# Platform specs

<!-- GENERATED from scripts/emitters/platform-specs.json by `brand-creator specs-due --write-markdown`. Do not edit by hand; a test fails when this file and the JSON disagree. -->

The sizes every emitter reads, with where each one comes from. Status: **V** re-verified at the source, **R** read from a secondary source, **U** unverified (recheck before relying on it; an emitter that uses a U or stale row says so in its report and in `assets/manifest.json`). A row is stale when `checked` is older than 180 days. `checked` records a person reading the source, never a script run. Re-verify every row before a release (`brand-creator specs-due`).

## Contents

- [favicon-search](#favicon-search)
- [favicon-set](#favicon-set)
- [pwa-manifest](#pwa-manifest)
- [open-graph](#open-graph)
- [github-social](#github-social)
- [readme-header](#readme-header)
- [downscale-apple](#downscale-apple)
- [apple-app-icon](#apple-app-icon)
- [apple-icon-composer](#apple-icon-composer)
- [apple-marketing-icon](#apple-marketing-icon)
- [apple-macos-iconset](#apple-macos-iconset)
- [apple-visionos-stack](#apple-visionos-stack)
- [apple-menubar-template](#apple-menubar-template)
- [apple-dmg-background](#apple-dmg-background)
- [apple-store-frames](#apple-store-frames)
- [windows-ico](#windows-ico)
- [windows-nsis](#windows-nsis)
- [windows-tray](#windows-tray)
- [tauri-icons](#tauri-icons)
- [linux-hicolor](#linux-hicolor)
- [linux-tray](#linux-tray)
- [linux-appstream](#linux-appstream)
- [apple-wallet](#apple-wallet)
- [google-wallet](#google-wallet)
- [email-logo](#email-logo)
- [nuget-icon](#nuget-icon)
- [github-org-avatar](#github-org-avatar)
- [cli-identity](#cli-identity)
- [email-signature](#email-signature)
- [social-post-4x5](#social-post-4x5)
- [social-post-1x1](#social-post-1x1)
- [print-EU](#print-EU)
- [print-US](#print-US)
- [print-JP](#print-JP)

## Table

| row | surface | status | checked | source |
|---|---|---|---|---|
| favicon-search | Favicon in Google Search | V | 2026-10-17 | https://developers.google.com/search/docs/appearance/favicon-in-search |
| favicon-set | Favicon set (ico, svg, apple-touch) | R | 2026-10-17 | https://evilmartians.com/chronicles/how-to-favicon-in-2021-six-files-that-fit-most-needs |
| pwa-manifest | PWA web app manifest icons | V | 2026-10-17 | https://web.dev/articles/install-criteria |
| open-graph | Open Graph link preview image | V | 2026-10-17 | https://developers.facebook.com/docs/sharing/webmasters/images |
| github-social | GitHub repository social preview | V | 2026-10-17 | https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview |
| readme-header | README header image (light and dark) | U | 2026-10-17 | https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax |
| downscale-apple | System downscale sample sizes (Apple icon family) | U | 2026-10-17 | https://developer.apple.com/design/human-interface-guidelines/app-icons |
| apple-app-icon | Apple app icon (iOS, iPadOS, macOS, watchOS, visionOS) | V | 2026-10-17 | https://developer.apple.com/design/human-interface-guidelines/app-icons |
| apple-icon-composer | Icon Composer .icon, actool and ictool | R | 2026-10-17 | https://developer.apple.com/documentation/xcode/creating-your-app-icon-using-icon-composer |
| apple-marketing-icon | App Store marketing icon | U | 2026-10-17 | https://developer.apple.com/help/app-store-connect/reference/app-information/app-icon-specifications |
| apple-macos-iconset | macOS legacy icon set (AppIcon.appiconset and .icns) | U | 2026-10-17 | https://developer.apple.com/design/human-interface-guidelines/app-icons |
| apple-visionos-stack | visionOS app icon (solid image stack) | R | 2026-10-17 | https://developer.apple.com/design/human-interface-guidelines/app-icons |
| apple-menubar-template | macOS menu bar template image | U | 2026-10-17 | https://developer.apple.com/design/human-interface-guidelines/the-menu-bar |
| apple-dmg-background | macOS DMG window background | U | 2026-10-17 | https://github.com/create-dmg/create-dmg |
| apple-store-frames | App Store screenshot frames | U | 2026-10-17 | https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications |
| windows-ico | Windows .ico (Win32) | V | 2026-10-17 | https://learn.microsoft.com/en-us/windows/apps/design/style/iconography/app-icon-construction |
| windows-nsis | NSIS installer images | U | 2026-10-17 | https://nsis.sourceforge.io/Docs/Modern%20UI%202/Readme.html |
| windows-tray | Windows notification area icons | U | 2026-10-17 | https://learn.microsoft.com/en-us/windows/apps/design/style/iconography/app-icon-construction |
| tauri-icons | Tauri icons folder | U | 2026-10-17 | https://v2.tauri.app/reference/cli/#icon |
| linux-hicolor | Linux hicolor icon theme | U | 2026-10-17 | https://specifications.freedesktop.org/icon-theme-spec/latest/ |
| linux-tray | Linux tray (status notifier) icons | U | 2026-10-17 | https://specifications.freedesktop.org/icon-theme-spec/latest/ |
| linux-appstream | AppStream metainfo | U | 2026-10-17 | https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html |
| apple-wallet | Apple Wallet pass images | V | 2026-10-17 | https://developer.apple.com/design/human-interface-guidelines/wallet |
| google-wallet | Google Wallet logos | V | 2026-10-17 | https://developers.google.com/wallet/retail/loyalty-cards/resources/brand-guidelines |
| email-logo | E-mail header logo | U | 2026-10-17 | https://www.caniemail.com/features/html-img/ |
| nuget-icon | NuGet package icon | U | 2026-10-17 | https://learn.microsoft.com/en-us/nuget/reference/nuspec#icon |
| github-org-avatar | GitHub organisation avatar | U | 2026-10-17 | https://docs.github.com/en/organizations/managing-organization-settings/customizing-your-organizations-profile |
| cli-identity | CLI identity text (ANSI colours) | U | 2026-10-17 | https://www.w3.org/TR/WCAG22/#contrast-minimum |
| email-signature | HTML e-mail signature | U | 2026-10-17 | https://www.w3.org/TR/WCAG22/#contrast-minimum |
| social-post-4x5 | Social feed post and carousel slide, portrait 4:5 | U | 2026-10-17 | https://help.instagram.com/1631821640426723 |
| social-post-1x1 | Social feed post, square 1:1 | U | 2026-10-17 | https://help.instagram.com/1631821640426723 |
| print-EU | Print stationery, EU | U | 2026-10-17 | https://www.iso.org/standard/36631.html |
| print-US | Print stationery, US | U | 2026-10-17 | https://www.usps.com/business/prices.htm |
| print-JP | Print stationery, JP | U | 2026-10-17 | https://www.jisc.go.jp/eng/ |

## favicon-search

- Surface: Favicon in Google Search
- Status: V, checked 2026-10-17
- Source: https://developers.google.com/search/docs/appearance/favicon-in-search
- Sizes: `{"recommended_min_px": 48, "stable_path": "/favicon.ico"}`

Square, at least 8x8, more than 48x48 recommended. BMP, GIF, ICO, PNG, JPEG, PPM or TIFF; SVG is not listed. The favicon URL must stay stable, so /favicon.ico is never fingerprinted.

## favicon-set

- Surface: Favicon set (ico, svg, apple-touch)
- Status: R, checked 2026-10-17
- Source: https://evilmartians.com/chronicles/how-to-favicon-in-2021-six-files-that-fit-most-needs
- Sizes: `{"ico_layers": [16, 32, 48], "ico_html_sizes": "32x32", "apple_touch": 180}`

Secondary source. favicon.ico with 16, 32 and 48 layers, an icon.svg that switches with prefers-color-scheme, and a 180 px apple-touch-icon on an opaque ground.

## pwa-manifest

- Surface: PWA web app manifest icons
- Status: V, checked 2026-10-17
- Source: https://web.dev/articles/install-criteria
- Also: https://web.dev/articles/maskable-icon
- Sizes: `{"any": [192, 512], "maskable": 512, "maskable_safe_radius": 0.4, "monochrome": 512}`

192 and 512 are required. A separate maskable 512 keeps its content inside a circle of 40 percent of the size; never combine purposes on one file. A monochrome purpose is optional.

## open-graph

- Surface: Open Graph link preview image
- Status: V, checked 2026-10-17
- Source: https://developers.facebook.com/docs/sharing/webmasters/images
- Sizes: `{"width": 1200, "height": 630}`

At least 1200x630, 8 MB at most. Platforms cache by URL, so the file name carries a content hash and changes whenever the bytes change.

## github-social

- Surface: GitHub repository social preview
- Status: V, checked 2026-10-17
- Source: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview
- Sizes: `{"width": 1280, "height": 640}`

PNG, JPG or GIF under 1 MB, at least 640x320, 1280x640 is best. Uploaded by hand in the repository settings.

## readme-header

- Surface: README header image (light and dark)
- Status: U, checked 2026-10-17
- Source: https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax
- Sizes: `{"width": 1280, "height": 320}`

No platform specifies a README header size; 1280x320 is a convention (4:1, fits GitHub's content width at 2x). UNVERIFIED, recheck. Referenced with a <picture> element so the light and dark variants switch.

## downscale-apple

- Surface: System downscale sample sizes (Apple icon family)
- Status: U, checked 2026-10-17
- Source: https://developer.apple.com/design/human-interface-guidelines/app-icons
- Sizes: `{"px": [180, 120, 87, 58, 40, 29, 20, 16]}`

The sizes the downscale check samples from one master (home screen 180/120, settings 87/58, spotlight and notification 40/29, small 20/16). Taken from the packs' own downscale checks, not re-read at the source: the check measures a master at these sizes, it does not ship them. UNVERIFIED, recheck against the current HIG before relying on the list.

## apple-app-icon

- Surface: Apple app icon (iOS, iPadOS, macOS, watchOS, visionOS)
- Status: V, checked 2026-10-17
- Source: https://developer.apple.com/design/human-interface-guidelines/app-icons
- Sizes: `{"layout_px": 1024, "watchos_px": 1088, "visionos_px": 1024, "visionos_layers_max": 3, "appearances": ["default", "dark", "clear-light", "clear-dark", "tinted-light", "tinted-dark"]}`

Layered, unmasked square layers at 1024 px (watchOS 1088, circular mask; visionOS 1024, a background plus one or two layers, circular, no Display P3). The system applies the mask. Change log of the page: 2026-06-08. The watchOS size is not a default of any tool: pass it explicitly.

## apple-icon-composer

- Surface: Icon Composer .icon, actool and ictool
- Status: R, checked 2026-10-17
- Source: https://developer.apple.com/documentation/xcode/creating-your-app-icon-using-icon-composer
- Also: https://github.com/giginet/apple-icon-composer-skill
- Sizes: `{"min_target": 26, "actool_platforms": {"ios": "iphoneos", "macos": "macosx", "watchos": "watchos", "visionos": "xros"}, "ictool_platforms": ["iOS", "macOS", "watchOS"], "renditions": ["Default", "Dark", "TintedLight", "TintedDark", "ClearLight", "ClearDark"]}`

The .icon format is undocumented by Apple; the schema is the community one vendored under scripts/vendor/. ictool accepts only iOS, macOS and watchOS (visionOS and tvOS are rejected) and its output is already masked, so it is a preview, never the marketing icon or the .icns. actool compiles a bare .icon (platforms iphoneos, macosx, watchos) to Assets.car plus fallback PNGs (iphoneos) or an .icns of up to 256 px (macosx). Run on Xcode 27.0 beta; recheck on each Xcode release.

## apple-marketing-icon

- Surface: App Store marketing icon
- Status: U, checked 2026-10-17
- Source: https://developer.apple.com/help/app-store-connect/reference/app-information/app-icon-specifications
- Sizes: `{"px": 1024, "alpha": false}`

1024 px, square, opaque. The no-alpha rule comes from developer forums: Apple's page could not be fetched when the row was written. UNVERIFIED, recheck. The emitter flattens onto the brand ground and writes an RGB PNG with no alpha channel.

## apple-macos-iconset

- Surface: macOS legacy icon set (AppIcon.appiconset and .icns)
- Status: U, checked 2026-10-17
- Source: https://developer.apple.com/design/human-interface-guidelines/app-icons
- Sizes: `{"points": [16, 32, 128, 256, 512], "scales": [1, 2], "canvas_px": 1024, "body_px": 824}`

Ten PNGs (16, 32, 128, 256, 512 pt at 1x and 2x) for targets below macOS 26 and for a Tauri .icns; the rounded body is 824 of 1024 px (the Big Sur template). Taken from earlier packs and checked locally with iconutil (it accepted the ten files); not re-read at the source. UNVERIFIED, recheck.

## apple-visionos-stack

- Surface: visionOS app icon (solid image stack)
- Status: R, checked 2026-10-17
- Source: https://developer.apple.com/design/human-interface-guidelines/app-icons
- Sizes: `{"layer_px": 1024, "layers_max": 3, "safe_circle": 0.9}`

A back layer and one or two front layers in a solidimagestack, 1024 px each, masked to a circle by the system. The 0.9 safe circle is a rule from an earlier pack, not an Apple number: artwork stays inside 90 percent of the circle.

## apple-menubar-template

- Surface: macOS menu bar template image
- Status: U, checked 2026-10-17
- Source: https://developer.apple.com/design/human-interface-guidelines/the-menu-bar
- Sizes: `{"width": 32, "height": 36, "scale": 2}`

A one-colour template image (black plus alpha) drawn at 32x36 px, which is 16x18 pt at 2x. Size taken from an earlier pack; not re-read at the source. UNVERIFIED, recheck.

## apple-dmg-background

- Surface: macOS DMG window background
- Status: U, checked 2026-10-17
- Source: https://github.com/create-dmg/create-dmg
- Sizes: `{"width": 660, "height": 400, "scales": [1, 2]}`

A 660x400 window with a @2x file for Retina. A convention of DMG builders, not a platform rule. UNVERIFIED, recheck.

## apple-store-frames

- Surface: App Store screenshot frames
- Status: U, checked 2026-10-17
- Source: https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications
- Sizes: `{"frames": [{"name": "iphone", "width": 1206, "height": 2622}, {"name": "ipad", "width": 2064, "height": 2752}, {"name": "mac", "width": 2880, "height": 1800}, {"name": "tv", "width": 3840, "height": 2160}]}`

Pixel sizes used by an earlier pack for iPhone, iPad, Mac and Apple TV. Not re-read at the source: Apple changes the accepted sizes with each device. UNVERIFIED, recheck. The emitter draws the frame only (the mark, the name, one line of real copy and an empty screenshot area), never an invented interface.

## windows-ico

- Surface: Windows .ico (Win32)
- Status: V, checked 2026-10-17
- Source: https://learn.microsoft.com/en-us/windows/apps/design/style/iconography/app-icon-construction
- Sizes: `{"layers": [16, 24, 32, 48, 256]}`

Bare minimum layers 16, 24, 32, 48 and 256. PNG-compressed entries.

## windows-nsis

- Surface: NSIS installer images
- Status: U, checked 2026-10-17
- Source: https://nsis.sourceforge.io/Docs/Modern%20UI%202/Readme.html
- Sizes: `{"header": {"width": 150, "height": 57}, "sidebar": {"width": 164, "height": 314}, "bit_depth": 24}`

Header 150x57 and welcome sidebar 164x314 as 24-bit BMP (no alpha, no palette). Sizes from an earlier pack; not re-read at the source. UNVERIFIED, recheck.

## windows-tray

- Surface: Windows notification area icons
- Status: U, checked 2026-10-17
- Source: https://learn.microsoft.com/en-us/windows/apps/design/style/iconography/app-icon-construction
- Sizes: `{"px": [16, 20, 24, 32, 40, 48]}`

16 px at 100 percent display scaling and the larger sizes at 125, 150, 200, 250 and 300 percent. From an earlier pack. UNVERIFIED, recheck. One set per taskbar theme, light and dark.

## tauri-icons

- Surface: Tauri icons folder
- Status: U, checked 2026-10-17
- Source: https://v2.tauri.app/reference/cli/#icon
- Sizes: `{"png": {"32x32.png": 32, "128x128.png": 128, "128x128@2x.png": 256, "icon.png": 512}, "ico_order": [32, 16, 24, 48, 64, 256]}`

The files a tauri.conf.json icon list usually names: 32x32.png, 128x128.png, 128x128@2x.png, icon.png (512), icon.icns and icon.ico with the 32 px layer first. The output list of `tauri icon` is not documented on the CLI page; this is the list of an earlier pack. UNVERIFIED, recheck.

## linux-hicolor

- Surface: Linux hicolor icon theme
- Status: U, checked 2026-10-17
- Source: https://specifications.freedesktop.org/icon-theme-spec/latest/
- Sizes: `{"px": [16, 22, 24, 32, 48, 64, 128, 256, 512], "scalable": "scalable/apps"}`

hicolor/<size>x<size>/apps/<id>.png plus hicolor/scalable/apps/<id>.svg. The size list is from an earlier pack, not read from the specification. UNVERIFIED, recheck.

## linux-tray

- Surface: Linux tray (status notifier) icons
- Status: U, checked 2026-10-17
- Source: https://specifications.freedesktop.org/icon-theme-spec/latest/
- Sizes: `{"px": [22, 44]}`

22 px, and 44 px for 2x panels (how a host scales the 44 px file is not verified). One palette: panels vary, so check the result on the target panel. UNVERIFIED, recheck.

## linux-appstream

- Surface: AppStream metainfo
- Status: U, checked 2026-10-17
- Source: https://www.freedesktop.org/software/appstream/docs/chap-Metadata.html
- Sizes: `{"icon_min_px": 64, "required_fields": ["id", "name", "summary", "metadata_license", "project_license", "description", "launchable"]}`

A stub: the fields a software centre needs. Text fields come from FACTS.md only; a field with no fact is written as an empty element the owner must fill (and reported). Not read at the source. UNVERIFIED, recheck.

## apple-wallet

- Surface: Apple Wallet pass images
- Status: V, checked 2026-10-17
- Source: https://developer.apple.com/design/human-interface-guidelines/wallet
- Sizes: `{"scales": [2, 3], "logo": {"height": 50, "min_width": 50, "max_width": 160}, "primaryLogo": {"height": 30, "min_width": 30, "max_width": 126}, "secondaryLogo": {"height": 12, "min_width": 12, "max_width": 135}, "icon": {"width": 38, "height": 38}, "strip": {"width": 375, "height": 144}, "thumbnail": {"height": 90, "min_width": 60, "max_width": 90}, "background": {"width": 343, "height": 503}, "artwork": {"width": 358, "height": 448}, "footer": {"width": 268, "height": 15}, "order_logo_px": 300}`

Sizes are in points; supply PNG at @2x and @3x. The order-tracking merchant logo is 300x300 px and not transparent. The emitter writes the brand images (icon, logo, primaryLogo, secondaryLogo, order logo); strip, thumbnail, background, artwork and footer carry pass content and are not brand marks.

## google-wallet

- Surface: Google Wallet logos
- Status: V, checked 2026-10-17
- Source: https://developers.google.com/wallet/retail/loyalty-cards/resources/brand-guidelines
- Sizes: `{"logo_px": 660, "circle_margin": 0.15, "wide": {"width": 1280, "height": 400}}`

Logo at least 660x660 px, 1:1, a circular mask is applied (keep a 15 percent margin inside the circle); the wide logo is 1280x400 px (minimum height 400), transparent PNG.

## email-logo

- Surface: E-mail header logo
- Status: U, checked 2026-10-17
- Source: https://www.caniemail.com/features/html-img/
- Sizes: `{"display_height": 24, "scales": [1, 2, 3]}`

No platform sets a size. The logo is shown 24 px high (an earlier pack's choice) and supplied as @1x, @2x and @3x PNG, transparent. UNVERIFIED, recheck; --height overrides.

## nuget-icon

- Surface: NuGet package icon
- Status: U, checked 2026-10-17
- Source: https://learn.microsoft.com/en-us/nuget/reference/nuspec#icon
- Sizes: `{"px": 128, "max_bytes": 1048576}`

A PNG or JPEG of at most 1 MB; 128x128 is the commonly recommended size. Not re-read at the source. UNVERIFIED, recheck.

## github-org-avatar

- Surface: GitHub organisation avatar
- Status: U, checked 2026-10-17
- Source: https://docs.github.com/en/organizations/managing-organization-settings/customizing-your-organizations-profile
- Sizes: `{"px": 1024}`

No size rule was found: GitHub crops and shrinks one square image. 1024 px (a whole multiple of the coarse-grid masters) is a choice, not a rule. UNVERIFIED, recheck.

## cli-identity

- Surface: CLI identity text (ANSI colours)
- Status: U, checked 2026-10-17
- Source: https://www.w3.org/TR/WCAG22/#contrast-minimum
- Sizes: `{"min_contrast": 4.5, "grounds": {"light": "#ffffff", "dark": "#000000"}}`

A terminal's real ground is the user's choice. A 24-bit brand colour is used only where it reaches the WCAG 2.2 text contrast (4.5) on both a white and a black ground; otherwise the named ANSI colour is used. The two grounds are a proposal. UNVERIFIED as a terminal rule, recheck.

## email-signature

- Surface: HTML e-mail signature
- Status: U, checked 2026-10-17
- Source: https://www.w3.org/TR/WCAG22/#contrast-minimum
- Sizes: `{"min_contrast": 4.5, "logo_scales": [1, 2]}`

A table layout with inline styles and its own ground, so a client that darkens or inverts a message cannot change the pair. The text and the ground must reach WCAG 2.2 text contrast (4.5). The logo is an opaque PNG shown at the e-mail logo height (email-logo row) at 1x and 2x. UNVERIFIED as a mail-client rule, recheck.

## social-post-4x5

- Surface: Social feed post and carousel slide, portrait 4:5
- Status: U, checked 2026-10-17
- Source: https://help.instagram.com/1631821640426723
- Sizes: `{"width": 1080, "height": 1350, "ratio": "4:5"}`

1080 x 1350 px is the usual 4:5 portrait feed size (carousel slides share one ratio). Written from general knowledge, not read at the platform's page. UNVERIFIED, recheck.

## social-post-1x1

- Surface: Social feed post, square 1:1
- Status: U, checked 2026-10-17
- Source: https://help.instagram.com/1631821640426723
- Sizes: `{"width": 1080, "height": 1080, "ratio": "1:1"}`

1080 x 1080 px is the usual square feed size. Written from general knowledge, not read at the platform's page. UNVERIFIED, recheck.

## print-EU

- Surface: Print stationery, EU
- Status: U, checked 2026-10-17
- Source: https://www.iso.org/standard/36631.html
- Sizes: `{"business_card_mm": [85, 55], "paper": "A4", "paper_mm": [210, 297], "envelope": "DL", "envelope_mm": [220, 110], "bleed_mm": 3}`

UNVERIFIED. A4 and DL follow ISO 216 and ISO 269; 85 x 55 mm is the common European business card. The 3 mm bleed is a typical default, not a rule: ask the printer.

## print-US

- Surface: Print stationery, US
- Status: U, checked 2026-10-17
- Source: https://www.usps.com/business/prices.htm
- Sizes: `{"business_card_mm": [88.9, 50.8], "business_card_in": [3.5, 2], "paper": "Letter", "paper_mm": [215.9, 279.4], "paper_in": [8.5, 11], "envelope": "#10", "envelope_mm": [241.3, 104.775], "envelope_in": [9.5, 4.125], "bleed_mm": 3.175, "bleed_in": 0.125}`

UNVERIFIED. 3.5 x 2 in card, 8.5 x 11 in letter paper and the 9.5 x 4.125 in #10 envelope are the usual US sizes; the 0.125 in bleed is a typical default, not a rule: ask the printer.

## print-JP

- Surface: Print stationery, JP
- Status: U, checked 2026-10-17
- Source: https://www.jisc.go.jp/eng/
- Sizes: `{"business_card_mm": [91, 55], "paper": "A4", "paper_mm": [210, 297], "envelope": "DL", "envelope_mm": [220, 110], "bleed_mm": 3}`

UNVERIFIED. 91 x 55 mm is the usual Japanese business card, A4 is the office paper. Japanese post also uses the long-format envelopes (for example nagagata 3, 120 x 235 mm); DL is used here because the plan names DL and #10 only, so pass --envelope-mm for a local format. The 3 mm bleed is a typical default: ask the printer.
