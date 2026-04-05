# Legal Notices

**HeadMatch** – Version 0.4.5 (and later)  
**License**: GNU General Public License v3.0 (GPL-3.0)  
**Last reviewed**: April 5, 2026

## 1. License

HeadMatch is free and open-source software released under the **GNU General Public License Version 3** (or any later version at your option).

- Full license text: [LICENSE](LICENSE)
- You are free to use, study, modify, and distribute HeadMatch, provided you respect the GPL-3.0 terms (including making source code available when distributing modified versions).

## 2. Patents

HeadMatch does **not** implement any patented algorithms or proprietary mechanisms.

The project uses only **standard, public-domain digital signal processing techniques**, including:

- Logarithmic sweep generation
- Local-maxima cross-correlation for alignment
- Wiener-regularised frequency-response estimation
- RBJ Audio EQ Cookbook biquad formulas (public W3C note / Usenet 1998)
- Nelder-Mead optimization (1965 paper, public domain)
- Fixed-band GraphicEQ fitting on standard frequency grids (10-band / 31-band)
- Clone-target difference curves with 1 kHz normalization

No part of the codebase infringes known patents in the fields of headphone EQ, room correction, or audio measurement. The project deliberately stays within well-established, non-proprietary methods.

## 3. Third-Party Components & References

- **RBJ Audio EQ Cookbook** – Public domain. HeadMatch includes 241 reference tests that validate exact coefficient matching against the open cookbook.
- All other algorithms are original implementations or standard numerical methods.

No proprietary libraries, closed-source binaries, or patented third-party code are used.

## 4. Privacy & Data Protection

HeadMatch collects **no user data**, sends **no telemetry**, and performs **no cloud processing**.

- Optional network feature: fetching publicly available headphone measurement curves (HTTPS only, hard 5 MB response limit, strict URL validation).
- All measurements, fits, and exports happen entirely on your local machine.
- Fully compliant with GDPR (EU), CCPA/CPRA (California), and equivalent data-protection laws worldwide.

## 5. Export & Network Controls

- Network access is strictly limited to HTTPS.
- No file://, http:// (non-secure), or arbitrary protocol support.
- No execution of downloaded code.

## 6. Warranty & Liability

HeadMatch is provided **AS IS**, without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement.

In no event shall the authors or copyright holders be liable for any claim, damages, or other liability, whether in contract, tort, or otherwise, arising from, out of, or in connection with the software or the use or other dealings in the software.

See the full GPL-3.0 license for details.

## 7. Trademarks

"HeadMatch" is not a registered trademark. Other product names and brands mentioned are the property of their respective owners.

## 8. Contact for Legal Questions

If you have any questions or concerns regarding patents, licensing, or legal compliance:

- Open an issue on the [GitHub repository](https://github.com/easeit-cz/headmatch) (preferred)
- Or contact the maintainers via the repository’s discussion channels

---

**This document is part of the official documentation of HeadMatch.**  
It is intended to provide transparency and due diligence for users, contributors, distributors, and packagers.
