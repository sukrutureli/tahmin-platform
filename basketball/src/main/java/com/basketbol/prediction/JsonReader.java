package com.basketbol.prediction;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.file.Files;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.*;

public class JsonReader {

    private static final ObjectMapper mapper = new ObjectMapper();

    /**
     * 🔹 JSON oku (local veya GitHub'dan)
     * @param source "github" veya "local"
     * @param folderName örn: "futbol"
     * @param prefix örn: "data-" veya ""
     * @param date tarih ("2025-11-12" formatında)
     * @param clazz JSON içeriği türü (örnek: PredictionData.class)
     */
    public static <T> List<T> read(String source, String folderName, String prefix, String date, Class<T> clazz) {
        try {
            if ("github".equalsIgnoreCase(source)) {
                return readFromGithub(folderName, prefix, date, clazz);
            } else {
                return readLocal(folderName, prefix, date, clazz);
            }
        } catch (Exception e) {
            System.out.println("⚠️ JSON okuma hatası: " + e.getMessage());
            return Collections.emptyList();
        }
    }

    /**
     * 🔹 Local JSON okuma
     */
    public static <T> List<T> readLocal(String folderName, String prefix, String date, Class<T> clazz) {
        File file = new File("public/" + folderName + "/data/" + prefix + date + ".json");
        if (!file.exists()) {
            System.out.println("⚠️ Dosya bulunamadı: " + file.getAbsolutePath());
            return Collections.emptyList();
        }

        try {
            byte[] jsonBytes = Files.readAllBytes(file.toPath());
            return mapper.readerForListOf(clazz).readValue(jsonBytes);
        } catch (IOException e) {
            e.printStackTrace();
            return Collections.emptyList();
        }
    }

    /**
     * 🔹 GitHub raw URL üzerinden JSON okuma
     * Örnek: https://raw.githubusercontent.com/{user}/{repo}/main/{folder}/data/{prefix}{date}.json
     */
    public static <T> List<T> readFromGithub(String folderName, String prefix, String date, Class<T> clazz)
            throws IOException {

        String user = "sukrutureli";
        String repo = "fathertahmin";
        String branch = "main";

        String url = String.format(
                "https://api.github.com/repos/%s/%s/contents/%s/data/%s-%s.json?ref=%s",
                user, repo, folderName, prefix, date, branch);

        System.out.println("📥 GitHub'dan indiriliyor: " + url);

        // Token kullan (gizli repo için)
        String token = System.getenv("GITHUB_TOKEN");
        HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
        conn.setRequestMethod("GET");
        conn.setConnectTimeout(15000);
        conn.setReadTimeout(30000);
        if (token != null && !token.isEmpty()) {
            conn.setRequestProperty("Authorization", "token " + token);
        }
        conn.setRequestProperty("Accept", "application/vnd.github.raw+json");

        int status = conn.getResponseCode();
        if (status == 401 || status == 403) {
            throw new IOException("GitHub access denied: HTTP " + status);
        }
        if (status != 200) {
        	System.out.println(String.format("⚠️ Dosya bulunamadı: %d", status));
        	return List.of();
        }

        try (InputStream in = conn.getInputStream()) {
            return mapper.readerForListOf(clazz).readValue(in);
        } 
    }

    /**
     * 🔹 Bugünün tarihini otomatik getir (İstanbul saatine göre)
     */
    public static String getToday() {
        LocalTime now = LocalTime.now(ZoneId.of("Europe/Istanbul"));
        LocalDate date = (now.isAfter(LocalTime.MIDNIGHT) && now.isBefore(LocalTime.of(6, 0)))
                ? LocalDate.now(ZoneId.of("Europe/Istanbul")).minusDays(1)
                : LocalDate.now(ZoneId.of("Europe/Istanbul"));
        return date.format(DateTimeFormatter.ofPattern("yyyy-MM-dd"));
    }
}
