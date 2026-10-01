package com.basketbol.experiment;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import com.basketbol.scraper.ResultApiClient;
import com.basketbol.scraper.HistoryApiClient;
import java.nio.file.*;
import java.time.Instant;
import java.io.IOException;

/** Refresh labels after predictions are frozen; artifact files only, no Application or Telegram. */
public final class OutcomeRefresh {
 public static void main(String[] args) throws Exception {
  ObjectMapper mapper=new ObjectMapper();Path replay=Path.of(args[0]);
  ArrayNode rows=(ArrayNode)mapper.readTree(replay.toFile());ArrayNode audit=mapper.createArrayNode();
  ResultApiClient client=new ResultApiClient();int fetched=0;
  for(JsonNode row:rows){
   if(!"holdout".equals(row.path("role").asText()))continue;
   ObjectNode entry=mapper.createObjectNode();entry.put("eventId",row.path("eventId").asText());
   entry.put("observedAt",Instant.now().toString());entry.set("snapshotScore",row.path("realScore"));audit.add(entry);
   try{
    String score=client.finishedScore("https://istatistik.nesine.com/"+row.path("eventId").asText()+"/ozet",2);
    if(score!=null){((ObjectNode)row).put("realScore",score);((ObjectNode)row).put("resultSource","live HTTP finished scoreboard");entry.put("score",score);entry.put("status","finished");fetched++;}
    else entry.put("status","not finished; frozen final retained if present");
   }catch(IOException ex){entry.put("status","request failed; frozen final retained if present");entry.put("error",ex.getMessage());
    if(ex instanceof HistoryApiClient.RateLimitException){entry.put("cooldownStopped",true);break;}
   }
  }
  mapper.writerWithDefaultPrettyPrinter().writeValue(replay.toFile(),rows);
  mapper.writerWithDefaultPrettyPrinter().writeValue(Path.of(args[1]).toFile(),audit);
  System.out.println("Artifact outcome refresh: attempted="+audit.size()+", finished="+fetched);
 }
}
