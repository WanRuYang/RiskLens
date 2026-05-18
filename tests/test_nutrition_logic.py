import unittest
from risklens_score import nutrition_score_from_text

class TestNutritionLogic(unittest.TestCase):
    def test_high_sugar_high_fat_label(self):
        # Input provided by the user
        label_text = """
        Nutrition Facts
        Serving size: 2 tbsp (37g)
        Calories: 200
        Total fat: 11g 14% DV
        Saturated fat: 4g 20% DV
        Total sugars: 21g
        Added sugars: 19g 38% DV
        Sodium: 15mg 1% DV
        Total carb: 22g 8% DV
        Protein: 2g
        """
        
        score_bar = nutrition_score_from_text(label_text)
        
        self.assertIsNotNone(score_bar)
        print(f"\nTested Grade: {score_bar.score}")
        print(f"Signals: {score_bar.riskSignals}")
        print(f"Description: {score_bar.description}")
        
        # Expected: Grade D or E
        self.assertIn(score_bar.score, ["D", "E"])
        
        # Expected flags
        signals_text = " ".join(score_bar.riskSignals)
        self.assertIn("High added sugar", signals_text)
        self.assertIn("High total sugar density", signals_text)
        self.assertIn("High saturated fat", signals_text)
        self.assertIn("Low sodium", signals_text)

if __name__ == "__main__":
    unittest.main()
