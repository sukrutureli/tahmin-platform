package com.example.prediction;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Collections;
import java.util.List;

public class JsonStorage {

	private static final ObjectMapper mapper = new ObjectMapper().enable(SerializationFeature.INDENT_OUTPUT);

	/**
	 * Generic kaydetme metodu: herhangi bir tipte listeyi JSON’a yazar.
	 */
	public static <T> void save(String folderName, String prefix, String date, List<T> data) throws IOException {
		//String today = LocalDate.now(ZoneId.of("Europe/Istanbul")).format(DateTimeFormatter.ofPattern("yyyy-MM-dd"));

		File folder = new File("public/" + folderName + "/data");
		if (!folder.exists())
			folder.mkdirs();

		File file = new File(folder, prefix + "-" + date + ".json");
		mapper.writeValue(file, data);

		System.out.println("✅ JSON kaydedildi: " + file.getAbsolutePath());
	}

	/**
	 * Generic okuma metodu: JSON dosyasını belirtilen tipte nesnelere çevirir.
	 */
	public static <T> List<T> read(String folderName, String prefix, String date, Class<T> clazz) {
		File file = new File("public/" + folderName + "/data/" + prefix + "-" + date + ".json");
		if (!file.exists()) {
			System.out.println("⚠️ Dosya bulunamadı: " + file.getAbsolutePath());
			return Collections.emptyList();
		}
		try {
			return mapper.readerForListOf(clazz).readValue(Files.readAllBytes(file.toPath()));
		} catch (IOException e) {
			e.printStackTrace();
			return Collections.emptyList();
		}
	}
}
