package com.basketbol.html;

import com.basketbol.MatchHistoryManager;
import com.basketbol.model.*;
import com.basketbol.util.MathUtils;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;

public class CombinedHtmlReportGenerator {

	/**
	 * Tek HTML içinde: 1) Üstte 💰 Kupon tablosu 2) Altta 🏀 Detaylı basketbol
	 * tahminleri
	 */
	public static void generateCombinedHtml(List<LastPrediction> sublistPredictions, List<MatchInfo> matches,
			MatchHistoryManager historyManager, List<Match> matchStats, // Şu an kullanılmıyor ama imzada dursun
			List<PredictionResult> results, List<PredictionData> sublistPredictionData, String fileName, String day,
			List<RealScores> realScores) {

		ZoneId istanbulZone = ZoneId.of("Europe/Istanbul");

		StringBuilder html = new StringBuilder();
		html.append("<!DOCTYPE html><html lang='tr'><head><meta charset='UTF-8'>");
		html.append(
				"<meta name='viewport' content='width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no'>");
		html.append("<title>🏀 Basketbol Tahminleri + 💰 Hazır Kupon</title>");
		html.append("<style>");

		// === GENEL LAYOUT =====================================================
		html.append("body{margin:0;padding:0;font-family:'Segoe UI',Roboto,Arial,sans-serif;")
				.append("background:#f3f6fa;color:#222;}");
		html.append(".page{max-width:1200px;margin:0 auto;padding:16px 10px;}");
		html.append(".day-title{text-align:center;color:#004d80;margin:12px 0 16px;font-size:24px;font-weight:700;}");
		html.append(".section{margin:20px 0;}");
		html.append(".section-title{text-align:center;color:#333;font-size:22px;margin-bottom:8px;}");
		html.append(".divider{border:none;border-top:3px solid #0077cc;margin:24px 0;}");

		// === KUPON TABLOSU (SUBLIST) =========================================
		html.append(".table-wrapper{width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch;margin-top:10px;}");
		html.append("table{width:100%;border-collapse:collapse;min-width:650px;background:#fff;border-radius:8px;")
				.append("box-shadow:0 2px 8px rgba(0,0,0,0.1);}");
		html.append("th,td{padding:10px 12px;text-align:center;border:1px solid #ddd;font-size:0.9rem;}");
		html.append("th{background:#0077cc;color:#fff;font-size:0.95rem;}");
		html.append("tr:nth-child(even){background:#f3f6fa;}");
		html.append("tr:hover{background:#eaf3ff;}");
		html.append(".status-icon{font-size:1.1em;}");
		html.append(".won{color:#28a745;}.lost{color:#dc3545;}.pending{color:#999;}");

		// === DETAYLI MATCH CARD LAYOUT =======================================
		html.append(".match{background:#fff;border:1px solid #dce3ec;margin:18px 0;padding:18px;")
				.append("border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.08);}");
		html.append(".match:hover{transform:translateY(-2px);box-shadow:0 4px 10px rgba(0,0,0,0.12);}");
		html.append(".match.insufficient{background-color:#fff1f1;border-left:4px solid #dc3545;}");

		html.append(".match-header{display:flex;justify-content:space-between;align-items:center;")
				.append("flex-wrap:wrap;margin-bottom:10px;}");
		html.append(".match-name{font-weight:700;color:#003366;font-size:1.3em;line-height:1.2;}");
		html.append(".match-time{color:#004d80;font-size:1.1em;font-weight:600;}");

		// Odds grid
		html.append(".odds-mini{background:#f8fafc;border:1px solid #dbe2ea;padding:12px;")
				.append("border-radius:10px;margin:14px 0;}");
		html.append(".odds-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;}");
		html.append(".odds-cell{background:#fff;border:1px solid #ccd6e0;border-radius:8px;padding:8px;")
				.append("text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.06);}");
		html.append(".highlight{background:#e9f9ec;border-color:#28a745!important;}");
		html.append(".odds-label{font-weight:700;color:#004d80;font-size:0.95em;display:inline-block;}");
		html.append(".odds-value{display:inline-block;font-weight:600;color:#111;font-size:0.9em;margin-left:4px;}");
		html.append(".odds-line{margin-bottom:4px;}");
		html.append(".odds-pct{display:block;color:#555;font-size:0.82em;margin-top:2px;}");

		// Quick summary
		html.append(".quick-summary{margin-top:10px;overflow-x:auto;-webkit-overflow-scrolling:touch;}");
		html.append(".quick-summary table.qs{width:100%;min-width:650px;border-collapse:collapse;background:#fff;")
				.append("border:1px solid #ccd6e0;border-radius:8px;overflow:hidden;}");
		html.append(".quick-summary th,.quick-summary td{padding:8px;text-align:center;border:1px solid #e1e7ef;}");
		html.append(".quick-summary th{background:#f0f5fb;color:#003366;font-weight:600;font-size:0.9rem;}");
		html.append(".qs-odd{font-variant-numeric:tabular-nums;color:#333;font-size:0.9rem;}");
		html.append(".qs-pick .pick{display:inline-block;padding:3px 10px;border-radius:12px;")
				.append("background:#e7f1ff;color:#004d80;font-weight:700;font-size:0.9rem;}");
		html.append(".qs-score{color:#111;font-weight:600;}");

		// Team stats + genel istatistik
		html.append(".team-stats{background:#e3f2fd;color:#0c5460;padding:10px 12px;border-radius:6px;")
				.append("margin:8px 0;font-size:0.9em;}");
		html.append(".stats{background:#fff;border:1px solid #dbe2ea;padding:18px;margin:20px 0;")
				.append("border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.05);}");
		html.append(".stats h3{color:#004d80;margin-top:0;font-size:1.1rem;}");

		// Responsive
		html.append("@media (max-width:600px){");
		html.append(".odds-grid{grid-template-columns:repeat(2,1fr);}");
		html.append(".match-name{font-size:1.1em;}");
		html.append(".match-time{font-size:1em;}");
		html.append("}");

		html.append("</style></head><body>");
		html.append("<div class='page'>");

		// === GÜN BAŞLIĞI ======================================================
		html.append("<div class='day-title'>").append(day).append("</div>");

		// ======================================================================
		// 1) KUPON BÖLÜMÜ
		// ======================================================================
		html.append("<section id='coupon' class='section'>");
		html.append("<h2 class='section-title'>💰 Basketbol Kuponu</h2>");
		html.append("<p style='text-align:center;color:#555;'>Sistemin oluşturduğu öneri kuponu</p>");
		html.append("<div class='table-wrapper'>");
		html.append("<table><thead><tr>");
		html.append("<th>🕒 Saat</th><th>🏀 Maç</th><th>🎯 Tahmin</th>")
				.append("<th>📊 Skor Tahmini</th><th>📈 Gerçek Skor</th><th>Durum</th>");
		html.append("</tr></thead><tbody>");

		for (int i = 0; i < sublistPredictions.size(); i++) {
			LastPrediction p = sublistPredictions.get(i);
			PredictionData d = (sublistPredictionData != null && i < sublistPredictionData.size())
					? sublistPredictionData.get(i)
					: null;

			String actualScore = (d != null && d.getScore() != null) ? d.getScore() : "-";

			StringBuilder statusIcons = new StringBuilder();
			if (d != null && p.getPredictions() != null) {
				for (String pick : p.getPredictions()) {
					String st = d.getStatuses() != null ? d.getStatuses().getOrDefault(pick, "pending") : "pending";
					switch (st) {
					case "won" -> statusIcons.append("<span class='status-icon won'>✅</span>");
					case "lost" -> statusIcons.append("<span class='status-icon lost'>❌</span>");
					default -> statusIcons.append("<span class='status-icon pending'>⏳</span>");
					}
				}
			} else {
				statusIcons.append("<span class='status-icon pending'>⏳</span>");
			}

			html.append("<tr>");
			html.append("<td>").append(p.getTime()).append("</td>");
			html.append("<td>").append(p.getName()).append("</td>");
			html.append("<td>").append(p.preditionsToString()).append("</td>");
			html.append("<td>").append(p.getScore() != null ? p.getScore() : "-").append("</td>");
			html.append("<td>").append(actualScore).append("</td>");
			html.append("<td>").append(statusIcons).append("</td>");
			html.append("</tr>");
		}

		html.append("</tbody></table>");
		html.append("</div>"); // .table-wrapper

		// === Kupon Win Rate Hesabı ===
		int won = 0;
		int lost = 0;
		int pending = 0;

		for (int i = 0; i < sublistPredictions.size(); i++) {
			PredictionData d = (sublistPredictionData != null && i < sublistPredictionData.size())
					? sublistPredictionData.get(i)
					: null;

			if (d != null && d.getStatuses() != null) {
				for (String pick : sublistPredictions.get(i).getPredictions()) {
					String st = d.getStatuses().getOrDefault(pick, "pending");
					if (st.equals("won"))
						won++;
					else if (st.equals("lost"))
						lost++;
					else
						pending++;
				}
			} else {
				pending++;
			}
		}

		// Win-rate: Sadece sonuçlanmışlar arasında hesaplanır
		double winRate = (won + lost) > 0 ? (won * 100.0 / (won + lost)) : 0.0;

		html.append("<div style='margin-top:12px; text-align:center;'>");
		html.append("<div style='display:inline-block; background:#fff; padding:12px 18px; border-radius:10px;");
		html.append("box-shadow:0 2px 8px rgba(0,0,0,0.10); border-left:5px solid #0077cc;'>");

		html.append("<p style='margin:0; font-size:1rem; color:#004d80; font-weight:700;'>Kupon Kazanma Yüzdesi</p>");
		html.append("<p style='margin:4px 0 0 0; font-size:0.95rem; color:#333;'>");
		html.append("Kazanan Tahmin: ").append(won);
		html.append(" • Kaybeden: ").append(lost);
		html.append(" • Bekleyen: ").append(pending);
		html.append("</p>");

		html.append("<p style='margin:6px 0 0 0; font-size:1.1rem; font-weight:700; color:#0077cc;'>");
		html.append(String.format("%.1f%%", winRate)).append("</p>");

		html.append("</div>");
		html.append("</div>");

		html.append("</section>");

		// Ayracı
		html.append("<hr class='divider'>");

		// ======================================================================
		// 2) DETAYLI MAÇ ANALİZİ BÖLÜMÜ
		// ======================================================================
		html.append("<section id='detail' class='section'>");
		html.append("<h2 class='section-title'>🏀 Basketbol Tahminleri</h2>");
		html.append("<p style='text-align:center;color:#555;margin-bottom:16px;'>Son güncelleme: ")
				.append(LocalDateTime.now(istanbulZone)).append("</p>");

		// İstatistikler
		int detailUrlCount = 0;
		int processedTeamCount = 0;
		for (MatchInfo match : matches) {
			if (match.hasDetailUrl()) {
				detailUrlCount++;
			}
		}

		html.append("<div class='stats'>");
		html.append("<h3>İstatistikler</h3>");
		html.append("<p>- Toplam maç: ").append(matches.size()).append("</p>");
		html.append("<p>- Detay URL'si olan: ").append(detailUrlCount).append("</p>");
		html.append("<p>- Geçmiş verisi çekilecek: ").append(detailUrlCount).append("</p>");
		html.append("</div>");

		// Maçlar
		for (int i = 0; i < matches.size(); i++) {
			MatchInfo match = matches.get(i);
			TeamMatchHistory teamHistory = historyManager.getTeamHistories().get(i);

			boolean insufficient = (teamHistory != null && !teamHistory.isInfoEnough()
					&& !teamHistory.isInfoEnoughWithoutRekabet());

			String homeStr = match.getName().split(" - ")[0];
			String awayStr = match.getName().split(" - ")[1];

			html.append("<div class='match").append(insufficient ? " insufficient" : "").append("'>");

			html.append("<div class='match-header'>");
			html.append("<div class='match-name'>").append(match.getName())
					.append(getRealScore(realScores, homeStr, awayStr)).append("</div>");
			html.append("<div class='match-time'>").append(match.getTime()).append("</div>");
			html.append("</div>");

			if (teamHistory != null && teamHistory.getTotalMatches() > 0) {
				html.append("<div class='odds-mini'>");
				html.append("<h4>Güncel Oranlar ve Yüzdeler</h4>");
				html.append("<div class='odds-grid'>");

				// MS1 – MS2 – H1 – H2
				html.append("<div class='odds-cell' style='")
						.append(teamHistory.getStyle("MS1", match.getOdds().getMs1())).append("'>");
				html.append("<div class='odds-line'><span class='odds-label'>MS1:</span>")
						.append("<span class='odds-value'>").append(match.getOdds().getMs1()).append("</span></div>");
				html.append("<span class='odds-pct'>").append(MathUtils.fmtPct(teamHistory.getMs1()))
						.append("</span></div>");

				html.append("<div class='odds-cell' style='")
						.append(teamHistory.getStyle("MS2", match.getOdds().getMs2())).append("'>");
				html.append("<div class='odds-line'><span class='odds-label'>MS2:</span>")
						.append("<span class='odds-value'>").append(match.getOdds().getMs2()).append("</span></div>");
				html.append("<span class='odds-pct'>").append(MathUtils.fmtPct(teamHistory.getMs2()))
						.append("</span></div>");

				html.append("<div class='odds-cell ").append(teamHistory.getStyle("H1", match.getOdds().getH1Value()))
						.append("'>");
				html.append("<div class='odds-line'><span class='odds-label'>H1 (").append(match.getOdds().getH1Value())
						.append("):</span>").append("<span class='odds-value'>").append(match.getOdds().getH1())
						.append("</span></div></div>");

				html.append("<div class='odds-cell ").append(teamHistory.getStyle("H2", match.getOdds().getH2Value()))
						.append("'>");
				html.append("<div class='odds-line'><span class='odds-label'>H2 (").append(match.getOdds().getH2Value())
						.append("):</span>").append("<span class='odds-value'>").append(match.getOdds().getH2())
						.append("</span></div></div>");

				html.append("</div>"); // odds-grid (MS/H)

				// Alt / Üst
				html.append("<div class='odds-grid' style='margin-top:8px;'>");

				html.append("<div class='odds-cell' style='")
						.append(teamHistory.getStyle("Alt", match.getOdds().getUnder())).append("'>");
				html.append("<div class='odds-line'><span class='odds-label'>Alt (")
						.append(match.getOdds().gethOverUnderValue()).append("):</span>")
						.append("<span class='odds-value'>").append(match.getOdds().getUnder()).append("</span></div>");
				html.append("<span class='odds-pct'>").append(MathUtils.fmtPct(teamHistory.getAlt()))
						.append("</span></div>");

				html.append("<div class='odds-cell' style='")
						.append(teamHistory.getStyle("Üst", match.getOdds().getOver())).append("'>");
				html.append("<div class='odds-line'><span class='odds-label'>Üst (")
						.append(match.getOdds().gethOverUnderValue()).append("):</span>")
						.append("<span class='odds-value'>").append(match.getOdds().getOver()).append("</span></div>");
				html.append("<span class='odds-pct'>").append(MathUtils.fmtPct(teamHistory.getUst()))
						.append("</span></div>");

				html.append("</div>"); // odds-grid (Alt/Üst)
				html.append("</div>"); // odds-mini

				int rekabet = teamHistory.getRekabetGecmisi().size();
				int home = teamHistory.getSonMaclarHome().size();
				int away = teamHistory.getSonMaclarAway().size();

				if (home > 0 && away > 0 && i < results.size()) {
					html.append("<div class='quick-summary'>");
					html.append("<table class='qs'><thead><tr>");
					html.append(
							"<th>MS1</th><th>MS2</th><th>Alt</th><th>Üst</th><th>Tahmin</th><th>Skor</th><th>Güven</th>");
					html.append("</tr></thead><tbody><tr>");
					html.append("<td class='qs-odd'>").append(MathUtils.fmtPct(results.get(i).getpHome()))
							.append("</td>");
					html.append("<td class='qs-odd'>").append(MathUtils.fmtPct(results.get(i).getpAway()))
							.append("</td>");
					html.append("<td class='qs-odd'>").append(MathUtils.fmtPct(1 - results.get(i).getpOver25()))
							.append("</td>");
					html.append("<td class='qs-odd'>").append(MathUtils.fmtPct(results.get(i).getpOver25()))
							.append("</td>");
					html.append("<td class='qs-pick'><span class='pick'>").append(results.get(i).getPick())
							.append("</span></td>");
					html.append("<td class='qs-score'>").append(results.get(i).getScoreline()).append("</td>");
					html.append("<td class='qs-odd'>").append(MathUtils.fmtPct(results.get(i).getConfidence()))
							.append("</td>");
					html.append("</tr></tbody></table></div>");
				}

				html.append("<div class='team-stats'>Bakılan maç sayısı: Rekabet - ").append(rekabet)
						.append(" | Ev sahibi - ").append(home).append(" | Deplasman - ").append(away).append("</div>");

				processedTeamCount++;
			} else {
				html.append("<div class='no-data'>Bu maç için geçmiş veri bulunamadı</div>");
			}

			html.append("</div>"); // .match
		}

		// Final istatistikleri
		html.append("<div class='stats'>");
		html.append("<h3>Final İstatistikleri</h3>");
		html.append("<p>- Toplam maç: ").append(matches.size()).append("</p>");
		html.append("<p>- Detay URL'si olan: ").append(detailUrlCount).append("</p>");
		html.append("<p>- Başarıyla geçmişi çekilen: ").append(processedTeamCount).append("</p>");
		html.append("<p>- Toplam takım: ").append(historyManager.getTotalTeams()).append("</p>");
		html.append("<p>- Başarı oranı: ").append(
				detailUrlCount > 0 ? String.format("%.1f%%", (processedTeamCount * 100.0 / detailUrlCount)) : "0%")
				.append("</p>");
		html.append("</div>");

		html.append("<p style='text-align:center;color:#666;margin-top:24px;'>");
		html.append("Bu veriler otomatik olarak çekilmiştir - Son güncelleme: ")
				.append(LocalDateTime.now(istanbulZone));
		html.append("</p>");

		html.append("</section>"); // detail
		html.append("</div>"); // .page
		html.append("</body></html>");

		// === DOSYA YAZMA ======================================================
		File dir = new File("public/basketbol");
		if (!dir.exists()) {
			dir.mkdirs();
		}
		File output = new File(dir, fileName);

		try (FileWriter fw = new FileWriter(output)) {
			fw.write(html.toString());
		} catch (IOException e) {
			e.printStackTrace();
		}

		System.out.println("✅ Birleşik basketbol HTML üretildi: " + output.getAbsolutePath());
	}

	// Detaylı kısımda skor yanına parantez içinde gerçek skor yazmak için
	private static String getRealScore(List<RealScores> rsList, String home, String away) {
		String score = " (⏳)";
		int count = 0;

		if (rsList != null) {
			for (RealScores rs : rsList) {
				if (home.equals(rs.getHomeTeam()) && away.equals(rs.getAwayTeam())) {
					score = " (" + rs.getScore() + ")";
					count = 1;
					break;
				}
				if (home.equals(rs.getHomeTeam()) || away.equals(rs.getAwayTeam())) {
					score = " (" + rs.getScore() + ")";
					count++;
				}
			}
			if (count != 1)
				score = " (⏳)";
		}
		return score;
	}
}
