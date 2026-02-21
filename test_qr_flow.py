from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # Step 1: Navigate to login page
    print("Step 1: Navigating to login page...")
    page.goto('http://localhost:3001/login')
    page.wait_for_load_state('networkidle')
    page.screenshot(path='C:/Users/USER/wa_assist/screenshots/01_login_page.png', full_page=True)
    print("Login page loaded")

    # Step 2: Fill in login credentials
    print("Step 2: Logging in...")
    page.fill('input[type="email"]', 'test@example.com')
    page.fill('input[type="password"]', 'testpassword123')
    page.screenshot(path='C:/Users/USER/wa_assist/screenshots/02_login_filled.png', full_page=True)

    # Step 3: Submit login
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')
    time.sleep(2)
    page.screenshot(path='C:/Users/USER/wa_assist/screenshots/03_after_login.png', full_page=True)
    print(f"After login, URL: {page.url}")

    # Step 4: Navigate to WhatsApp page
    print("Step 4: Navigating to WhatsApp page...")
    page.goto('http://localhost:3001/instances')
    page.wait_for_load_state('networkidle')
    time.sleep(2)
    page.screenshot(path='C:/Users/USER/wa_assist/screenshots/04_whatsapp_page.png', full_page=True)
    print("WhatsApp page loaded")

    # Step 5: Click "Connect WhatsApp" button
    print("Step 5: Clicking Connect WhatsApp...")
    connect_btn = page.locator('button:has-text("Connect WhatsApp")').first
    if connect_btn.is_visible():
        connect_btn.click()
        time.sleep(1)
        page.screenshot(path='C:/Users/USER/wa_assist/screenshots/05_connect_dialog.png', full_page=True)
        print("Connect dialog opened")
    else:
        print("ERROR: Connect WhatsApp button not found")
        # Take a screenshot to debug
        page.screenshot(path='C:/Users/USER/wa_assist/screenshots/05_error_no_button.png', full_page=True)
        browser.close()
        exit(1)

    # Step 6: Enter connection name
    print("Step 6: Entering connection name...")
    name_input = page.locator('input#connection-name')
    if name_input.is_visible():
        name_input.fill('test-browser-qr')
        page.screenshot(path='C:/Users/USER/wa_assist/screenshots/06_name_entered.png', full_page=True)
        print("Name entered")
    else:
        print("ERROR: Connection name input not found")
        page.screenshot(path='C:/Users/USER/wa_assist/screenshots/06_error_no_input.png', full_page=True)
        browser.close()
        exit(1)

    # Step 7: Click "Get QR Code" button
    print("Step 7: Clicking Get QR Code...")
    qr_btn = page.locator('button:has-text("Get QR Code")')
    if qr_btn.is_visible():
        qr_btn.click()
        # Wait for the QR code to load
        print("Waiting for QR code response...")
        time.sleep(8)
        page.screenshot(path='C:/Users/USER/wa_assist/screenshots/07_qr_code_result.png', full_page=True)
        print("QR code step complete")
    else:
        print("ERROR: Get QR Code button not found")
        page.screenshot(path='C:/Users/USER/wa_assist/screenshots/07_error_no_qr_btn.png', full_page=True)
        browser.close()
        exit(1)

    # Step 8: Check if QR code image rendered
    print("Step 8: Checking QR code rendering...")
    qr_img = page.locator('img[alt="WhatsApp QR Code"]')
    if qr_img.is_visible():
        # Check the image dimensions to verify it rendered
        box = qr_img.bounding_box()
        if box and box['width'] > 50 and box['height'] > 50:
            print(f"SUCCESS: QR code rendered! Size: {box['width']}x{box['height']}")
        else:
            print(f"WARNING: QR code image found but may not have rendered. Box: {box}")

        # Get the src attribute to check format
        src = qr_img.get_attribute('src')
        if src:
            print(f"Image src starts with: {src[:60]}...")
            if src.startswith('data:image/png;base64,iVBOR'):
                print("SUCCESS: QR code has correct base64 PNG format")
            elif src.startswith('data:image/png;base64,data:'):
                print("ERROR: Double-prefixed data URL detected!")
            else:
                print(f"Image src format: {src[:80]}")
        else:
            print("WARNING: No src attribute on image")
    else:
        print("ERROR: QR code image not visible")
        # Check if there's a broken image or loading state
        all_imgs = page.locator('img').all()
        print(f"Total images on page: {len(all_imgs)}")
        for i, img in enumerate(all_imgs):
            alt = img.get_attribute('alt') or 'no-alt'
            src = (img.get_attribute('src') or 'no-src')[:80]
            print(f"  Image {i}: alt='{alt}', src='{src}'")

    # Final screenshot
    page.screenshot(path='C:/Users/USER/wa_assist/screenshots/08_final_state.png', full_page=True)

    # Cleanup: try to delete the test instance
    print("\nCleaning up test instance...")
    # We'll do this via API since we're already done with the UI test

    browser.close()
    print("\nTest complete! Check screenshots in C:/Users/USER/wa_assist/screenshots/")
