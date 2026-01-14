from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import os

file_path = "~/Documents/Automation/project/destination.txt"
# Expand the tilde before opening
expanded_path = os.path.expanduser(file_path)

with open(expanded_path, 'r', encoding='utf-8') as file:
    content = file.read()
    print(content)

n = "Jaypee Institute of Information technology, sector 128"

# --- CONFIGURATION ---
options = UiAutomator2Options()
options.platform_name = "Android"
options.automation_name = "UiAutomator2"
options.udid = "RZ8N50GJNER" 

# Start with Rapido
options.app_package = "com.rapido.passenger"
options.app_activity = "com.rapido.passenger.DefaultAlias"

options.no_reset = True
options.dont_stop_app_on_reset = True 
options.set_capability("appium:newCommandTimeout", 300)
options.set_capability("appium:appWaitActivity", "*")
options.set_capability("appium:forceAppLaunch", True)
options.set_capability("appium:shouldTerminateApp", True)

try:
    print("Connecting to device...")
    driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
    wait = WebDriverWait(driver, 20)
    
    # --- RAPIDO SECTION ---
    print("App launched. Waiting for 'Where are you going?' button...")
    where_to_button = wait.until(EC.presence_of_element_located(
        (AppiumBy.ACCESSIBILITY_ID, "Where are you going?")
    ))

    print("Clicking Rapido Search...")
    where_to_button.click()
    time.sleep(5)

    print("Typing destination...")
    actions = ActionChains(driver)
    actions.send_keys(n)
    actions.perform()

    # Trigger Search Action
    driver.execute_script('mobile: performEditorAction', {'action': 'search'})
    time.sleep(5)

    # Tap the result
    print("Tapping coordinate (480, 800)...")
    driver.tap([(480, 800)], 500)
    time.sleep(5)

    driver.save_screenshot("new_device_rapido.png")
    print("Rapido part complete!")

    # --- UBER SECTION ---
    print("\nSwitching to Uber now...")
    
    # activate_app is the modern way to swap apps in Appium 3.x
    driver.activate_app("com.ubercab")
    
    # Give Uber time to load its splash screen and home screen
    time.sleep(8) 

    wait = WebDriverWait(driver, 5)
    element = wait.until(EC.element_to_be_clickable((AppiumBy.XPATH, '//android.widget.FrameLayout[@resource-id="com.ubercab:id/ub__top_bar_mode_navigation"]/android.widget.FrameLayout/com.uber.rib.core.compose.root.UberComposeView/android.view.View/android.view.View/android.view.View[2]/d5.g/android.widget.FrameLayout/androidx.compose.ui.platform.ComposeView/android.view.View/android.view.View[1]')))
    element.click()

    time.sleep(2)
    actions.send_keys("Jaypee Institute of Information Technology, sector 128")
    actions.perform()

    # Trigger Search Action
    driver.execute_script('mobile: performEditorAction', {'action': 'search'})
    time.sleep(2)

    driver.tap([(430, 750)], 500)
    time.sleep(8)



    
    driver.save_screenshot("uber_opened.png")
    print("Uber is now open and active!")

    input("Task complete. Press Enter to close the session...")

except Exception as e:
    print(f"Error: {e}")

# finally:
#    driver.quit()
#    if 'driver' in locals():
#        driver.quit()
