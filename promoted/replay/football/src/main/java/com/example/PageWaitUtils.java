package com.example;

import org.openqa.selenium.*;
import org.openqa.selenium.support.ui.*;

import java.time.Duration;

public class PageWaitUtils {

	public static void safeWaitForLoad(WebDriver driver, int timeoutSeconds) {
		WebDriverWait wait = new WebDriverWait(driver, Duration.ofSeconds(timeoutSeconds));
		try {
			wait.until(d -> ((JavascriptExecutor) d).executeScript("return document.readyState").equals("complete"));
		} catch (Exception ignored) {
		}
		try {
			wait.until(ExpectedConditions.presenceOfElementLocated(By.tagName("body")));
		} catch (Exception ignored) {
		}
	}

	public static boolean safeClick(WebDriver driver, By locator, int timeoutSeconds) {
		try {
			WebElement el = new WebDriverWait(driver, Duration.ofSeconds(timeoutSeconds))
					.until(ExpectedConditions.elementToBeClickable(locator));
			el.click();
			return true;
		} catch (Exception e) {
			return false;
		}
	}

	public static void waitForPageLoad(WebDriver driver, int timeoutSeconds) {
		new WebDriverWait(driver, Duration.ofSeconds(timeoutSeconds))
				.until(webDriver -> ((JavascriptExecutor) webDriver).executeScript("return document.readyState")
						.equals("complete"));
	}

	public static boolean safeClick(WebDriver driver, WebElement element, int seconds) {
		try {
			WebDriverWait wait = new WebDriverWait(driver, Duration.ofSeconds(seconds));
			wait.until(ExpectedConditions.elementToBeClickable(element));
			element.click();
			return true;
		} catch (Exception e) {
			return false;
		}
	}

}
