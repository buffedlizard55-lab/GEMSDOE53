#!/usr/bin/env python3
"""Optional real-browser desktop/mobile check (Playwright + local Chromium)."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000/docs/')
    parser.add_argument('--config', default='work/browser-check/browser.json')
    args = parser.parse_args()
    cfg = json.loads((ROOT / args.config).read_text())
    env = {**os.environ, **cfg.get('env', {})}
    libs = ROOT / 'work/browser-check/libs/lib'
    if libs.exists():
        env['LD_LIBRARY_PATH'] = str(libs) + ':' + env.get('LD_LIBRARY_PATH', '')
    result = {'engine': 'real Chromium via NPM fallback after blocked CDN', 'screens': []}
    receipt = json.loads((ROOT / 'evidence/submission_r2.json').read_text())
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=cfg['executablePath'],
            args=[a for a in cfg['args'] if a != '--single-process'], env=env, headless=True)
        for label, width, height in [('desktop', 1440, 1000), ('mobile', 390, 844)]:
            context = browser.new_context(viewport={'width': width, 'height': height}, permissions=['clipboard-read', 'clipboard-write'])
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(args.url, wait_until='networkidle')
            page.screenshot(path=str(ROOT / f'work/browser-check/{label}.png'), full_page=True)
            assert page.locator('.download-bar a[download]').count() == 1
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), f'{label}: overflow'
            assert not errors, errors
            with page.expect_download() as pending:
                page.locator('.download-bar a[download]').click()
            target = ROOT / f'work/browser-check/{label}.tif'
            pending.value.save_as(str(target))
            assert hashlib.sha256(target.read_bytes()).hexdigest() == receipt['sha256']
            page.goto(args.url + 'executive-summary.html', wait_until='networkidle')
            assert 'NOT APPROVED' in page.locator('.download-bar').inner_text()
            assert page.locator('#submission-note').input_value() == receipt['note']
            page.locator('[data-copy]').click()
            expect(page.locator('[data-copy]')).to_have_text('Copied')
            assert page.evaluate('navigator.clipboard.readText()') == receipt['note']
            result['screens'].append(dict(viewport=label, width=width, js_errors=errors,
                download_sha256=receipt['sha256'], horizontal_overflow=False, note_and_clipboard_match=True))
            context.close()
        browser.close()
    (ROOT / 'evidence/browser_review_r2.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
