"""
Quick test: generates mockup 1 only using the single image set.
Run: python test_mockup.py
Check: OUTPUT/single/mockups/single_mockup_1.jpg
"""
import logging, sys, os
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.mockup_generator import generate_mockups

images = ["INPUT/single/WB-EX-32-Edward_Robert_Hughes_Midsummer-18x24.jpg"]
paths  = generate_mockups("INPUT/single", images, "OUTPUT")
print("\nGenerated:")
for p in paths:
    print(" ", p)
