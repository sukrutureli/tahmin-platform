package com.basketbol.experiment;
import com.basketbol.model.*;
import com.basketbol.algorithm.*;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.nio.file.*;
import java.util.*;
public class ExperimentReplay {
 public static void main(String[] args) throws Exception {
  ObjectMapper mapper=new ObjectMapper().configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES,false);
  JsonNode inputs=mapper.readTree(Path.of(args[0]).toFile());ArrayNode output=mapper.createArrayNode();
  List<BettingAlgorithm> active=List.of(new HeuristicPredictor(), new FormMomentumModel());
  List<BettingAlgorithm> evaluated=new ArrayList<>(active);evaluated.add(new EnsembleModel(active)); evaluated.add(new NormalizedFormModel()); evaluated.add(new EnsembleModel(List.of(new HeuristicPredictor(), new NormalizedFormModel())));
  for(JsonNode input:inputs){ObjectNode row=(ObjectNode)input.deepCopy();ObjectNode variants=mapper.createObjectNode();
   var fields=input.path("variants").fields();while(fields.hasNext()){
    var field=fields.next(); Match match=mapper.treeToValue(field.getValue().path("match"),Match.class); 
    ObjectNode variant=(ObjectNode)field.getValue().deepCopy();ObjectNode predictions=mapper.createObjectNode();
    for(BettingAlgorithm model:evaluated){PredictionResult result=model.predict(match,Optional.ofNullable(match.getOdds()));
     String key=model.name();if(model instanceof EnsembleModel && predictions.has(key)) key="EnsembleNormalizedForm";
     predictions.set(key,mapper.valueToTree(result));
    }
    variant.set("models",predictions); variants.set(field.getKey(),variant);
   }
   row.set("variants",variants);output.add(row);
  }
  mapper.writerWithDefaultPrettyPrinter().writeValue(Path.of(args[1]).toFile(),output);
  System.out.println("Replay records: "+output.size());
 }
}
