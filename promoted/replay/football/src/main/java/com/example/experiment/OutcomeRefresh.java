package com.example.experiment;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import com.example.scraper.ResultApiClient;
import com.example.scraper.HistoryApiClient;
import java.nio.file.*;
import java.time.Instant;
import java.io.IOException;
import java.util.concurrent.*;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** Refresh labels after predictions are frozen; artifact files only, no Application or Telegram. */
public final class OutcomeRefresh {
 public static void main(String[] args) throws Exception {
  ObjectMapper mapper=new ObjectMapper();Path replay=Path.of(args[0]);
  ArrayNode rows=(ArrayNode)mapper.readTree(replay.toFile());ArrayNode audit=mapper.createArrayNode();
  ResultApiClient client=new ResultApiClient();int fetched=0;
  long deadline=System.nanoTime()+TimeUnit.MINUTES.toNanos(12);
  ExecutorService executor=Executors.newSingleThreadExecutor(r->{Thread t=new Thread(r,"bounded-result-refresh");t.setDaemon(true);return t;});
  List<JsonNode> refreshRows=new ArrayList<>();rows.forEach(refreshRows::add);
  // Retry unresolved fixtures first; preserve original replay order and frozen forecasts.
  refreshRows.sort(Comparator.comparingInt(r->"live HTTP finished scoreboard".equals(r.path("resultSource").asText())?1:0));
  try {
  for(JsonNode row:refreshRows){
   if(!"holdout".equals(row.path("role").asText()))continue;
   if(args.length>2 && "--missing-only".equals(args[2]) && "live HTTP finished scoreboard".equals(row.path("resultSource").asText()))continue;
   ObjectNode entry=mapper.createObjectNode();entry.put("eventId",row.path("eventId").asText());
   entry.put("observedAt",Instant.now().toString());entry.set("snapshotScore",row.path("realScore"));audit.add(entry);
   long remaining=deadline-System.nanoTime();
   if(remaining<=0){entry.put("status","time budget; refresh stopped");break;}
   Future<String> pending=executor.submit(()->client.finishedScore("https://istatistik.nesine.com/"+row.path("eventId").asText()+"/ozet",1));
   try{
    String score=pending.get(Math.min(remaining,TimeUnit.SECONDS.toNanos(90)),TimeUnit.NANOSECONDS);
    if(score!=null){((ObjectNode)row).put("realScore",score);((ObjectNode)row).put("resultSource","live HTTP finished scoreboard");entry.put("score",score);entry.put("status","finished");fetched++;}
    else entry.put("status","not finished; frozen final retained if present");
   }catch(TimeoutException ex){pending.cancel(true);entry.put("status","request timeout; refresh stopped");break;
   }catch(ExecutionException ex){
    entry.put("status","request failed; frozen final retained if present");
    if(ex.getCause() instanceof HistoryApiClient.RateLimitException){entry.put("status","rate limit; refresh stopped");entry.put("cooldownStopped",true);break;}
    if(!(ex.getCause() instanceof IOException))throw ex;
   }
  }
  } finally {executor.shutdownNow();}
  mapper.writerWithDefaultPrettyPrinter().writeValue(replay.toFile(),rows);
  mapper.writerWithDefaultPrettyPrinter().writeValue(Path.of(args[1]).toFile(),audit);
  System.out.println("Artifact outcome refresh: attempted="+audit.size()+", finished="+fetched);
 }
}
