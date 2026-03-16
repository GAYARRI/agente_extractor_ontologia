from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import requests
import torch


class VisionPOIDetector:

    def __init__(self):

        self.model = CLIPModel.from_pretrained(
            "openai/clip-vit-base-patch32"
        )

        self.processor = CLIPProcessor.from_pretrained(
            "openai/clip-vit-base-patch32"
        )

        self.labels = [
            "a beach",
            "a castle",
            "a church",
            "a museum",
            "a mountain landscape",
            "a natural park",
            "a historical monument"
        ]


    def detect(self, image_url):

        try:

            response = requests.get(image_url, timeout=10)

            image = Image.open(
                requests.get(image_url, stream=True).raw
            ).convert("RGB")

        except Exception:

            return None


        inputs = self.processor(
            text=self.labels,
            images=image,
            return_tensors="pt",
            padding=True
        )

        outputs = self.model(**inputs)

        logits = outputs.logits_per_image

        probs = logits.softmax(dim=1)

        best = torch.argmax(probs)

        score = probs[0][best].item()

        label = self.labels[best]

        if score < 0.4:
            return None

        return {
            "label": label,
            "score": score
        }