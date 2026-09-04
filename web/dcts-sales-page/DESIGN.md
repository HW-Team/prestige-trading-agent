---
version: alpha
name: DCTS Prestige

description: Luxury, disciplined, evidence-led Thai trading education design system.
colors:
  primary: "#0F0F10"
  secondary: "#1D2A38"
  tertiary: "#C6A15B"
  neutral: "#F4F1EA"
  surface: "#141315"
  border: "rgba(244, 241, 234, 0.12)"
  muted: "rgba(244, 241, 234, 0.66)"
  positive: "#C6A15B"
  warning: "#D9BC7E"
typography:
  h1:
    fontFamily: Trirong
    fontSize: 4rem
    fontWeight: 700
    lineHeight: 1.08
    letterSpacing: "-0.035em"
  h2:
    fontFamily: Trirong
    fontSize: 2.5rem
    fontWeight: 700
    lineHeight: 1.16
    letterSpacing: "-0.025em"
  h3:
    fontFamily: Trirong
    fontSize: 1.5rem
    fontWeight: 650
    lineHeight: 1.3
  body-md:
    fontFamily: Sarabun
    fontSize: 1rem
    fontWeight: 400
    lineHeight: 1.75
  label:
    fontFamily: Montserrat
    fontSize: 0.875rem
    fontWeight: 600
    lineHeight: 1.4
rounded:
  sm: 6px
  md: 10px
  lg: 14px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 40px
  section: 112px
components:
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "#15110B"
    rounded: "{rounded.md}"
    padding: 14px
  button-primary-hover:
    backgroundColor: "#D9BC7E"
    textColor: "#15110B"
    rounded: "{rounded.md}"
    padding: 14px
  button-secondary:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.neutral}"
    rounded: "{rounded.md}"
    padding: 14px
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.neutral}"
    rounded: "{rounded.lg}"
    padding: 24px
---

## Overview

DCTS Prestige presents trading education as a disciplined learning system, not a shortcut to guaranteed income. The visual identity follows the original DTCS website: obsidian, ivory, Prestige gold, and deep navy. The interface must feel credible, private-club premium, and easy to scan on a phone.

## Colors

- Obsidian is the main page background.
- Ivory carries headings and high-contrast body text.
- Prestige gold is the only high-emphasis conversion accent.
- Deep navy is reserved for selected panels and serious financial context.
- Muted ivory keeps long-form Thai content readable.
- Warning is reserved for unconfirmed price and policy labels.

## Typography

Use Trirong for editorial Thai headings, Sarabun for Thai body copy, Montserrat for labels and CTA text, and Playfair Display for selected numbers. Headings are wide and editorial, with the hero limited to two or three lines. Body text is at least 16px with generous Thai line height.

## Layout

- Maximum content width: 1200px.
- Major sections use 112px desktop padding and 72px mobile padding.
- Hero is an editorial split with text left and a real or clearly decorative image right.
- The first mobile viewport must contain the core promise and one สมัคร DCTS action.
- Course modules and FAQs collapse into accessible accordions on mobile.

## Elevation & Depth

- Campaign imagery and the DCTS emblem are generated through Higgsfield under a controlled no-claims brief, then self-hosted as optimized SVG/WebP assets.
- The generated emblem is decorative branding, not evidence of results.
- Prefer ivory hairline borders and subtle tonal separation over large drop shadows. Use restrained gold glow only around the main offer and checkout preview.

## Shapes

- Cards: 14px.
- Buttons and controls: 10px.
- CTA buttons may be rounded but should not become oversized pills.
- Avoid decorative blobs, generic SaaS gradients, neon crypto cards, and fake trading-dashboard glass panels.

## Components

- `button-primary` is the only high-emphasis action and always reads สมัคร DCTS.
- Secondary actions support learning, such as ดูวิดีโอ 3 นาที.
- Asset slots are visibly labeled when real Coach, evidence, LMS, or testimonial media is missing.
- Offer pricing stays visually subordinate while marked รอยืนยันราคาและเงื่อนไข.

## Do's and Don'ts

Do:
- Show the checklist mechanism and learning process.
- Use documentary learner imagery only as decorative campaign media.
- Keep evidence dates, sample sizes, and methodology near each claim.
- Keep risk disclosure visible before and after checkout intent.

Do not:
- Promise a fixed return, profit, success rate, or risk-free outcome.
- Represent generated people as Coach Golf or real students.
- Use fake countdowns, fake seat scarcity, or an unverified list price.
- Expose a paid LINE access link in page source.
- Use neon crypto, casino, or luxury-car imagery.
