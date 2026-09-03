import json
import random
import os

# Create 75 rich, distinct Yeezy / Streetwear products

categories = ["sneakers", "apparel", "accessories"]

brands = ["Yeezy", "Adidas", "Nike", "Fear of God", "Off-White", "Supreme", "Balenciaga", "Travis Scott", "BAPE", "Rhude", "Palm Angels", "Stüssy", "Kith", "Heron Preston", "Vetements"]

# Real curated high quality unsplash image URLs for fashion/streetwear/sneakers/accessories
unsplash_sneakers = [
    "https://images.unsplash.com/photo-1552346154-21d32810aba3?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1600185365483-26d7a4cc7519?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1608231387042-66d1773070a5?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1607522370275-f14206abe5d3?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1539185441755-769473a23570?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1512374382149-233c42b6a83b?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1603808033192-082d6919d3e1?auto=format&fit=crop&q=80&w=800"
]

unsplash_apparel = [
    "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1509967419530-da38b4704bc6?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1578587018452-892bacefd3f2?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1618354691373-d851c5c3a990?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1516257984-b1b4d707412e?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1544441893-675973e31985?auto=format&fit=crop&q=80&w=800"
]

unsplash_accessories = [
    "https://images.unsplash.com/photo-1588850561407-ed78c282e89b?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1511499767150-a48a237f0083?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1622560480605-d83c853bc5c3?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&q=80&w=800"
]

# Definition of 75 products seed template
product_definitions = [
    # Sneakers & Slides (30 products)
    {"name": "Yeezy Boost 350 V2 'Zebra'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[0],
     "desc": "Iconic primeknit upper with distinctive black and white zebra stripes and red SPLY-350 accent.",
     "tags": ["yeezy", "sneakers", "zebra", "boost", "primeknit", "streetwear"],
     "specs": {"color": "White/Core Black/Red", "size_uk": 9, "material": "Primeknit", "sole": "Boost", "release_year": 2017}},
    
    {"name": "Yeezy Slide 'Bone'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[9],
     "desc": "Minimalist slide injected with EVA foam for lightweight durability and plush cushioning.",
     "tags": ["yeezy", "slides", "bone", "eva", "minimalist", "comfort"],
     "specs": {"color": "Bone", "size_uk": 8, "material": "EVA Foam", "water_resistant": True, "season": "SS22"}},
    
    {"name": "Yeezy Foam RNNR 'Onyx'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[1],
     "desc": "Futuristic molded slip-on shoe crafted from harvested algae and lightweight EVA foam.",
     "tags": ["yeezy", "foamrunner", "onyx", "futuristic", "eco", "black"],
     "specs": {"color": "Onyx Black", "size_uk": 10, "material": "EVA Foam & Algae", "ventilation": "High", "weight_g": 310}},

    {"name": "Yeezy Boost 700 'Wave Runner'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[2],
     "desc": "The dad-shoe archetype featuring multi-layered suede, mesh, and leather with vibrant teal accents.",
     "tags": ["yeezy", "700", "waverunner", "chunky", "boost", "grey"],
     "specs": {"color": "Solid Grey/Chalk White", "size_uk": 9.5, "material": "Suede & Mesh", "cushioning": "Full Length Boost"}},

    {"name": "Yeezy 500 'Utility Black'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[3],
     "desc": "Tonal monochromatic design blending premium suede, leather, and mesh atop an adiprene+ outsole.",
     "tags": ["yeezy", "500", "utilityblack", "adiprene", "monochrome"],
     "specs": {"color": "Utility Black", "size_uk": 8.5, "material": "Cow Suede & Nubuck", "cushioning": "adiprene+"}},

    {"name": "Yeezy Boost 380 'Alien'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[4],
     "desc": "Extraterrestrial pattern design with a sock-like Primeknit upper and re-engineered Boost midsole.",
     "tags": ["yeezy", "380", "alien", "boost", "camo"],
     "specs": {"color": "Alien White/Grey", "size_uk": 9, "material": "Primeknit", "midsole": "Translucent Boost"}},

    {"name": "Yeezy Quantum 'Barium'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[5],
     "desc": "High-top basketball hybrid sneaker engineered with synthetic suede toe cap and reflective heels.",
     "tags": ["yeezy", "quantum", "barium", "hightop", "basketball"],
     "specs": {"color": "Barium Dark Grey", "size_uk": 10.5, "material": "Jacquard Mesh & Suede", "ankle_support": "High"}},

    {"name": "Yeezy 450 'Cloud White'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[6],
     "desc": "Avant-garde design featuring a knit upper engulfed by a claw-like molded foam exoskeleton.",
     "tags": ["yeezy", "450", "cloudwhite", "exoskeleton", "knit"],
     "specs": {"color": "Cloud White", "size_uk": 9, "material": "Knit & PU Foam", "closure": "Lace-Up", "fit": "Snug"}},

    {"name": "Yeezy Slide 'Pure'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[9],
     "desc": "Neutral tan slip-on crafted with textured EVA foam and strategic groove traction.",
     "tags": ["yeezy", "slides", "pure", "tan", "minimalist"],
     "specs": {"color": "Pure Tan", "size_uk": 7, "material": "EVA Foam", "grip_pattern": "Deep Horizontal Grooves"}},

    {"name": "Yeezy Boost 350 V2 'Beluga 2.0'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[7],
     "desc": "Muted grey primeknit matrix with reverse orange SPLY-350 lettering across the lateral side.",
     "tags": ["yeezy", "350", "beluga", "boost", "grey"],
     "specs": {"color": "Grey/Bold Orange", "size_uk": 10, "material": "Primeknit", "sole": "Boost", "release_year": 2017}},

    {"name": "Air Jordan 1 Retro High OG 'Chicago Reimagined'", "brand": "Nike", "cat": "sneakers", "img": unsplash_sneakers[8],
     "desc": "Timeless basketball sneaker styled with distressed cracked leather detailing for a retro aesthetic.",
     "tags": ["nike", "jordan1", "chicago", "highog", "retro"],
     "specs": {"color": "Varsity Red/Black/Sail", "size_uk": 9.5, "material": "Cracked Leather", "profile": "High-Top"}},

    {"name": "Nike Dunk Low 'Panda'", "brand": "Nike", "cat": "sneakers", "img": unsplash_sneakers[0],
     "desc": "Versatile classic streetwear dunk featuring two-tone black and white full-grain leather upper.",
     "tags": ["nike", "dunklow", "panda", "blackwhite", "leather"],
     "specs": {"color": "Black/White", "size_uk": 8, "material": "Leather", "sole": "Rubber Cupsole"}},

    {"name": "Off-White x Nike Air Force 1 'MCA'", "brand": "Off-White", "cat": "sneakers", "img": unsplash_sneakers[1],
     "desc": "Virgil Abloh's iconic blue leather AF1 with metallic silver swoosh and signature zip tie.",
     "tags": ["offwhite", "nike", "af1", "mca", "virgilabloh", "blue"],
     "specs": {"color": "University Blue/Silver", "size_uk": 10, "material": "Leather", "accent": "Red Zip Tie"}},

    {"name": "Travis Scott x Air Jordan 1 Low 'Reverse Mocha'", "brand": "Travis Scott", "cat": "sneakers", "img": unsplash_sneakers[2],
     "desc": "Collaborative low-top sneaker featuring reverse swoosh logo and premium brown nubuck overlays.",
     "tags": ["travisscott", "jordan1", "reversemocha", "cactusjack"],
     "specs": {"color": "Sail/Dark Mocha", "size_uk": 9, "material": "Nubuck & Leather", "special_box": True}},

    {"name": "Balenciaga Triple S 'Clear Sole Black'", "brand": "Balenciaga", "cat": "sneakers", "img": unsplash_sneakers[3],
     "desc": "Chunky triple-stacked sole sneaker with athletic mesh base and embroidered size on the toe.",
     "tags": ["balenciaga", "triples", "chunky", "luxury", "black"],
     "specs": {"color": "Black", "size_eu": 43, "material": "Mesh & Leather", "weight_kg": 1.4, "sole": "Triple Layer TPU"}},

    {"name": "Fear of God California Slip-On 'Oatmeal'", "brand": "Fear of God", "cat": "sneakers", "img": unsplash_sneakers[9],
     "desc": "Sculpted slip-on shoe handmade in Italy from closed-cell foam with a minimalist rear backstop.",
     "tags": ["fearofgod", "california", "slipon", "oatmeal", "minimal"],
     "specs": {"color": "Oatmeal", "size_eu": 42, "material": "Closed-Cell Foam", "origin": "Italy"}},

    {"name": "Yeezy Slide 'Onyx'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[9],
     "desc": "Stealthy matte black EVA foam slide offering comfort, durability, and easy slip-on wear.",
     "tags": ["yeezy", "slides", "onyx", "black", "foam"],
     "specs": {"color": "Matte Black", "size_uk": 9, "material": "EVA Foam", "waterproof": True}},

    {"name": "Yeezy 700 V3 'Azael'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[4],
     "desc": "Futuristic low-top with glow-in-the-dark RPU cage overlay and monofilament woven upper.",
     "tags": ["yeezy", "700v3", "azael", "glowinthedark", "rpu"],
     "specs": {"color": "Azael Off-White", "size_uk": 9, "material": "Engineered Monofilament & RPU", "feature": "Glow-In-The-Dark"}},

    {"name": "Yeezy Boost 350 V2 'Dazzling Blue'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[5],
     "desc": "Core black Primeknit upper punctuated with a striking royal blue lateral stripe and SPLY logo.",
     "tags": ["yeezy", "350", "dazzlingblue", "boost", "black"],
     "specs": {"color": "Core Black/Dazzling Blue", "size_uk": 10, "material": "Primeknit", "sole": "Boost"}},

    {"name": "Adidas Adilette 22 Slides 'Desert Sand'", "brand": "Adidas", "cat": "sneakers", "img": unsplash_sneakers[9],
     "desc": "3D topographic map-inspired slides constructed with bio-based EVA material containing sugarcane.",
     "tags": ["adidas", "adilette22", "desertsand", "3d", "eco"],
     "specs": {"color": "Desert Sand", "size_uk": 8, "material": "Bio-EVA", "texture": "Topographic 3D"}},

    {"name": "BAPE STA Low 'White Black'", "brand": "BAPE", "cat": "sneakers", "img": unsplash_sneakers[6],
     "desc": "Japanese streetwear classic crafted in glossy patent leather with the signature STA star motif.",
     "tags": ["bape", "bapesta", "patentleather", "star", "tokyo"],
     "specs": {"color": "White/Black", "size_jp": 27.5, "material": "Patent Leather", "star_logo": "Stitched"}},

    {"name": "Yeezy Foam RNNR 'Vermilion'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[1],
     "desc": "Vibrant all-red molded foam runner delivering an eye-catching avant-garde silhouette.",
     "tags": ["yeezy", "foamrunner", "vermilion", "red", "statement"],
     "specs": {"color": "Vermilion Red", "size_uk": 9, "material": "EVA & Algae", "weight_g": 315}},

    {"name": "Yeezy Boost 700 V2 'Static'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[7],
     "desc": "Reflective 3M side stripes integrated across pale grey mesh and premium cream leather panels.",
     "tags": ["yeezy", "700v2", "static", "3m", "reflective"],
     "specs": {"color": "Static Grey/Cream", "size_uk": 9.5, "material": "Mesh, Suede & Leather", "reflective_3m": True}},

    {"name": "Air Jordan 4 Retro 'Military Black'", "brand": "Nike", "cat": "sneakers", "img": unsplash_sneakers[8],
     "desc": "Clean color-blocked high top featuring smooth white leather, neutral grey suede, and black accents.",
     "tags": ["nike", "jordan4", "militaryblack", "retro", "basketball"],
     "specs": {"color": "White/Black/Neutral Grey", "size_uk": 10, "material": "Full-Grain Leather", "air_unit": "Visible Air"}},

    {"name": "Yeezy Knit Runner 'Stone Carbon'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[4],
     "desc": "Seamless laceless sock silhouette enveloped in fully knitted fabric with sizing printed at collar.",
     "tags": ["yeezy", "knitrunner", "stonecarbon", "laceless", "knit"],
     "specs": {"color": "Stone Carbon/Mustard", "size_uk": 9, "material": "Structured Knit", "fit": "True to size"}},

    {"name": "Kith x Asics Gel-Lyte III 'Super Blue'", "brand": "Kith", "cat": "sneakers", "img": unsplash_sneakers[0],
     "desc": "Ronnie Fieg designed retro runner with rich suede uppers and Gel cushioning system.",
     "tags": ["kith", "asics", "gellyte", "ronniefieg", "suede"],
     "specs": {"color": "Super Blue/Grey", "size_uk": 8.5, "material": "Pigskin Suede", "cushioning": "Gel Tech"}},

    {"name": "Yeezy Boost 350 V2 'Onyx'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[5],
     "desc": "Triple black Primeknit execution paired with semi-translucent TPU midsole encapsulation.",
     "tags": ["yeezy", "350", "onyx", "tripleblack", "stealth"],
     "specs": {"color": "Onyx Black", "size_uk": 9, "material": "Primeknit", "sole": "Encapsulated Boost"}},

    {"name": "Off-White OOO 'Out of Office' Sneaker", "brand": "Off-White", "cat": "sneakers", "img": unsplash_sneakers[6],
     "desc": "Retro-inspired low top leather trainer featuring contrasting arrow emblem and tag detail.",
     "tags": ["offwhite", "outofoffice", "arrow", "luxury", "whitegreen"],
     "specs": {"color": "White/Green", "size_eu": 42, "material": "Calfskin Leather", "closure": "Lace-up"}},

    {"name": "Yeezy Slide 'Flax'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[9],
     "desc": "Earthy copper brown tone slip-on engineered with lightweight injected EVA foam.",
     "tags": ["yeezy", "slides", "flax", "earthtone", "comfort"],
     "specs": {"color": "Flax Brown", "size_uk": 11, "material": "EVA Foam", "finish": "Textured"}},

    {"name": "Yeezy Boost 700 'MNVN Metallic'", "brand": "Yeezy", "cat": "sneakers", "img": unsplash_sneakers[3],
     "desc": "No-sew polyester upper with oversized metallic silver 700 graphic and bungee infinity laces.",
     "tags": ["yeezy", "mnvn", "metallic", "bungeelace", "polyester"],
     "specs": {"color": "Metallic Silver/Black", "size_uk": 9, "material": "Minimally-stitched Nylon", "laces": "Bungee"}},


    # Apparel - Hoodies, Sweatpants, Tees, Jackets (25 products)
    {"name": "Fear of God Essentials Oversized Hoodie", "brand": "Fear of God", "cat": "apparel", "img": unsplash_apparel[0],
     "desc": "Heavyweight fleece hoodie styled with dropped shoulders and rubberized logo patch on the hood.",
     "tags": ["fog", "essentials", "hoodie", "oversized", "streetwear", "fleece"],
     "specs": {"color": "Stretch Limo Black", "size": "L", "material": "80% Cotton / 20% Polyester", "fit": "Oversized Heavyweight"}},

    {"name": "Yeezy Gap Engineered by Balenciaga Puffer Jacket", "brand": "Yeezy", "cat": "apparel", "img": unsplash_apparel[1],
     "desc": "Sculptural outerwear piece featuring an exaggerated cropped silhouette and matte nylon shell.",
     "tags": ["yeezy", "gap", "balenciaga", "puffer", "jacket", "black"],
     "specs": {"color": "Matte Black", "size": "M", "material": "100% Nylon Shell", "filling": "90/10 Duck Down", "fit": "Boxy Cropped"}},

    {"name": "Supreme Box Logo Hooded Sweatshirt 'Heather Grey'", "brand": "Supreme", "cat": "apparel", "img": unsplash_apparel[2],
     "desc": "Heavyweight cross-grain cotton fleece hoodie featuring the iconic red embroidered box logo.",
     "tags": ["supreme", "boxlogo", "bogo", "hoodie", "heathergrey", "grail"],
     "specs": {"color": "Heather Grey", "size": "L", "material": "100% Heavyweight Cotton Fleece", "country_of_origin": "Canada"}},

    {"name": "Travis Scott Cactus Jack AstroWorld Hoodie", "brand": "Travis Scott", "cat": "apparel", "img": unsplash_apparel[3],
     "desc": "Official tour merch featuring front 'Look Mom I Can Fly' embroidery and back graphic print.",
     "tags": ["travisscott", "cactusjack", "astroworld", "hoodie", "merch"],
     "specs": {"color": "Black", "size": "XL", "material": "100% Cotton", "print": "Puff Print & Embroidery"}},

    {"name": "Off-White Caravaggio Arrow Oversized Tee", "brand": "Off-White", "cat": "apparel", "img": unsplash_apparel[4],
     "desc": "Classic jersey tee featuring Caravaggio renaissance artwork merged into the iconic cross arrows.",
     "tags": ["offwhite", "caravaggio", "tee", "arrows", "virgilabloh"],
     "specs": {"color": "White", "size": "M", "material": "100% Cotton Jersey", "fit": "Relaxed Oversized"}},

    {"name": "BAPE Shark Full-Zip Double Hoodie 'Green Camo'", "brand": "BAPE", "cat": "apparel", "img": unsplash_apparel[5],
     "desc": "Signature full-zip hoodie with WGM felt patches and embroidered shark jaws across the hood.",
     "tags": ["bape", "sharkhoodie", "greencamo", "fullzip", "harajuku"],
     "specs": {"color": "1st Camo Green", "size": "L", "material": "100% Cotton Fleece", "closure": "Dual Full-Zip"}},

    {"name": "Rhude Eagle Graphic Oversized Tee", "brand": "Rhude", "cat": "apparel", "img": unsplash_apparel[6],
     "desc": "Vintage washed heavy cotton t-shirt decorated with sun-faded eagle print and hand distressed hem.",
     "tags": ["rhude", "vintagewash", "eagle", "tee", "losangeles"],
     "specs": {"color": "Vintaged Charcoal", "size": "L", "material": "100% Carded Cotton", "wash": "Custom Sun Fade"}},

    {"name": "Palm Angels Curved Logo Sweatpants", "brand": "Palm Angels", "cat": "apparel", "img": unsplash_apparel[7],
     "desc": "Luxury lounge pants featuring signature arched gothic script logo across the rear seat.",
     "tags": ["palmangels", "sweatpants", "gothic", "lounge", "black"],
     "specs": {"color": "Black/White", "size": "M", "material": "100% French Terry Cotton", "waist": "Elasticated Drawstring"}},

    {"name": "Yeezy Season 6 Heavyweight Fleece Sweatpants", "brand": "Yeezy", "cat": "apparel", "img": unsplash_apparel[0],
     "desc": "Garment-dyed minimalist fleece pants designed with deep side pockets and elastic ankles.",
     "tags": ["yeezy", "season6", "sweatpants", "core", "garmentdyed"],
     "specs": {"color": "Core Brown", "size": "L", "material": "100% Garment-Dyed Cotton", "fit": "Relaxed Tapered"}},

    {"name": "Fear of God Essentials Fleece Short 'Desert Taupe'", "brand": "Fear of God", "cat": "apparel", "img": unsplash_apparel[4],
     "desc": "Lounge shorts with extended drawstrings and understated Essentials rubberized patch.",
     "tags": ["fog", "essentials", "shorts", "deserttaupe", "summer"],
     "specs": {"color": "Desert Taupe", "size": "M", "material": "80% Cotton / 20% Polyester", "inseam_inches": 7}},

    {"name": "Balenciaga Speed Hunters Matrix Hoodie", "brand": "Balenciaga", "cat": "apparel", "img": unsplash_apparel[2],
     "desc": "Ultra-oversized vintage washed hoodie displaying fictional boyband graphic across the chest.",
     "tags": ["balenciaga", "speedhunters", "hoodie", "oversized", "couture"],
     "specs": {"color": "Washed Black", "size": "S (Fits XL)", "material": "Heavy Cotton Fleece", "fit": "Extreme Oversized"}},

    {"name": "Stüssy Basic Logo Crewneck Sweatshirt", "brand": "Stüssy", "cat": "apparel", "img": unsplash_apparel[3],
     "desc": "Californian streetwear staple crewneck printed with Shawn Stussy's original signature logo.",
     "tags": ["stussy", "crewneck", "basiclogo", "ashgrey", "surfstreet"],
     "specs": {"color": "Ash Grey", "size": "L", "material": "80% Cotton / 20% Polyester", "neckline": "Ribbed Crew"}},

    {"name": "Kith Box Logo Williams III Hoodie", "brand": "Kith", "cat": "apparel", "img": unsplash_apparel[0],
     "desc": "500 GSM custom combed cotton fleece sweatshirt detailed with tonal embroidered chest logo.",
     "tags": ["kith", "williamsiii", "500gsm", "hoodie", "navy"],
     "specs": {"color": "Nocturnal Navy", "size": "L", "material": "500GSM Combed Cotton", "weight": "Ultra Heavyweight"}},

    {"name": "Heron Preston CTNMB Mock Neck Long Sleeve", "brand": "Heron Preston", "cat": "apparel", "img": unsplash_apparel[4],
     "desc": "Ribbed mock collar top stamped with Cyrillic 'STYLE' embroidery and orange sleeve patch.",
     "tags": ["heronpreston", "ctnmb", "mockneck", "orange", "cyrillic"],
     "specs": {"color": "Black/Orange", "size": "M", "material": "100% Organic Cotton", "collar": "Mock Neck"}},

    {"name": "Vetements 'Target' Oversized Graphic Tee", "brand": "Vetements", "cat": "apparel", "img": unsplash_apparel[6],
     "desc": "Subversive streetwear graphic tee cut with extreme shoulder drop and reinforced neckline.",
     "tags": ["vetements", "graphictee", "target", "highstreet", "overfit"],
     "specs": {"color": "Black", "size": "M", "material": "100% Heavy Jersey Cotton", "fit": "Vetements Boxy"}},

    {"name": "Yeezy Gap Engineered by Balenciaga Dove Hoodie", "brand": "Yeezy", "cat": "apparel", "img": unsplash_apparel[1],
     "desc": "Double-layered seamless hoodie adorned with a subtle faded white dove graphic on the back.",
     "tags": ["yeezy", "gap", "balenciaga", "dovehoodie", "washed"],
     "specs": {"color": "Washed Black", "size": "L", "material": "Double-Layered 100% Cotton", "feature": "Seamless Construction"}},

    {"name": "Travis Scott x Fragment Design T-Shirt", "brand": "Travis Scott", "cat": "apparel", "img": unsplash_apparel[3],
     "desc": "Triple collaboration tee pairing Cactus Jack imagery with Fragment's lightning bolt motif.",
     "tags": ["travisscott", "fragment", "cactusjack", "hiroshifujiwara"],
     "specs": {"color": "Aged Aged Cream", "size": "XL", "material": "100% Vintage Washed Cotton", "print": "Screenprint"}},

    {"name": "Supreme Motion Logo Hooded Sweatshirt", "brand": "Supreme", "cat": "apparel", "img": unsplash_apparel[2],
     "desc": "Fleece pullover highlighted by the blur-effect motion logo printed across the chest.",
     "tags": ["supreme", "motionlogo", "black", "hoodie", "skateboarding"],
     "specs": {"color": "Black", "size": "M", "material": "100% Cotton Fleece", "pocket": "Kangaroo Front"}},

    {"name": "Off-White Marker Pen Diagonal Zip Hoodie", "brand": "Off-White", "cat": "apparel", "img": unsplash_apparel[5],
     "desc": "Full zip jacket styled with marker-stroke diagonal lines down sleeves and cross back logo.",
     "tags": ["offwhite", "markerpen", "zipup", "diagonals", "black"],
     "specs": {"color": "Black/Fuchsia", "size": "L", "material": "100% French Terry Cotton", "closure": "Metal Zip"}},

    {"name": "Palm Angels Classic Track Jacket", "brand": "Palm Angels", "cat": "apparel", "img": unsplash_apparel[7],
     "desc": "Athletic track top featuring white striped trim along sleeves and gothic logo on front chest.",
     "tags": ["palmangels", "trackjacket", "stripes", "athleisure", "red"],
     "specs": {"color": "Bright Red", "size": "M", "material": "100% Polyester", "neck": "Funnel Collar"}},

    {"name": "Fear of God Essentials Thermal Henley Tee", "brand": "Fear of God", "cat": "apparel", "img": unsplash_apparel[4],
     "desc": "Waffle knit thermal shirt engineered with raw hem finishing and three-button placket.",
     "tags": ["fog", "essentials", "henley", "waffleknit", "layering"],
     "specs": {"color": "Concrete Grey", "size": "L", "material": "100% Waffle Cotton", "buttons": "Custom Rubberized"}},

    {"name": "BAPE ABC Camo Shark Sweatpants", "brand": "BAPE", "cat": "apparel", "img": unsplash_apparel[5],
     "desc": "All-over ABC camo print fleece jogger pants with printed shark mouth detailing on the crotch.",
     "tags": ["bape", "abccamo", "sharkpants", "green", "japanese"],
     "specs": {"color": "Green Camo", "size": "L", "material": "100% Cotton Fleece", "waist": "Drawstring"}},

    {"name": "Yeezy Season 5 Calabasas Track Pants", "brand": "Yeezy", "cat": "apparel", "img": unsplash_apparel[0],
     "desc": "Retro double-knit nylon track pants emblazoned with Calabasas text logo along side stripes.",
     "tags": ["yeezy", "calabasas", "trackpants", "retro", "nylon"],
     "specs": {"color": "Ink / Solar Red", "size": "M", "material": "100% Double-Knit Nylon", "zips": "Ankle Zippers"}},

    {"name": "Rhude Moonlight Tropical Hawaiian Shirt", "brand": "Rhude", "cat": "apparel", "img": unsplash_apparel[6],
     "desc": "Fluid silk-blend camp collar shirt printed with surreal night palm landscape artwork.",
     "tags": ["rhude", "hawaiianshirt", "campcollar", "silk", "summer"],
     "specs": {"color": "Multi Moonlight", "size": "L", "material": "60% Silk / 40% Cotton", "collar": "Camp Collar"}},

    {"name": "Supreme Cross Box Logo Tee", "brand": "Supreme", "cat": "apparel", "img": unsplash_apparel[3],
     "desc": "Limited holiday release tee displaying two overlapping Supreme red box logos in a cross layout.",
     "tags": ["supreme", "crossboxlogo", "white", "tee", "collectible"],
     "specs": {"color": "White", "size": "M", "material": "100% Cotton", "edition": "FW20 Special Release"}},


    # Accessories - Caps, Bags, Belts, Sunglasses, Socks, Jewelry (20 products)
    {"name": "Off-White Industrial Belt 'Yellow Black'", "brand": "Off-White", "cat": "accessories", "img": unsplash_accessories[0],
     "desc": "200cm iconic yellow nylon webbing belt featuring woven red stitching and heavy metal buckle.",
     "tags": ["offwhite", "industrialbelt", "yellow", "webbing", "virgilabloh", "statement"],
     "specs": {"color": "Yellow/Black", "length_cm": 200, "material": "Polyester Webbing", "buckle": "Heavy Duty Metal Clasp"}},

    {"name": "Yeezy Gap Flame Logo Cap", "brand": "Yeezy", "cat": "accessories", "img": unsplash_accessories[0],
     "desc": "Distressed dad hat styled with flame artwork enveloping the front bill and adjustable back strap.",
     "tags": ["yeezy", "gap", "flamecap", "hat", "distressed", "black"],
     "specs": {"color": "Black", "size": "Adjustable", "material": "100% Twill Cotton", "closure": "Metal Strap Slider"}},

    {"name": "Fear of God Essentials Crossbody Bag", "brand": "Fear of God", "cat": "accessories", "img": unsplash_accessories[1],
     "desc": "Compact shoulder bag crafted from matte waterproof nylon with rubberized Essentials badge.",
     "tags": ["fog", "essentials", "crossbody", "bag", "minimalist", "everyday"],
     "specs": {"color": "Matte Black", "capacity_l": 2.5, "material": "Waterproof Cordura Nylon", "strap": "Adjustable Webbing"}},

    {"name": "Supreme Canvas Backpack 'Black'", "brand": "Supreme", "cat": "accessories", "img": unsplash_accessories[1],
     "desc": "Durable Cordura ripstop nylon backpack with padded laptop sleeve and large step logo graphic.",
     "tags": ["supreme", "backpack", "cordura", "black", "carryall"],
     "specs": {"color": "Black", "capacity_l": 21, "material": "500D Cordura Nylon", "laptop_sleeve": "15-inch"}},

    {"name": "Balenciaga LED Frame Sunglasses", "brand": "Balenciaga", "cat": "accessories", "img": unsplash_accessories[2],
     "desc": "Cyberpunk square frames with multi-color illumination LED logo on the left temple arm.",
     "tags": ["balenciaga", "sunglasses", "led", "cyberpunk", "futuristic"],
     "specs": {"color": "Black/Clear LED", "uv_protection": "UV400 100%", "lens_color": "Grey", "frame_material": "Nylon Acetate"}},

    {"name": "BAPE ABC Camo Duffel Bag", "brand": "BAPE", "cat": "accessories", "img": unsplash_accessories[1],
     "desc": "Spacious weekend travel bag coated in green ABC ape camo pattern with leather carry handles.",
     "tags": ["bape", "duffelbag", "travel", "abccamo", "streetwear"],
     "specs": {"color": "Green Camo", "capacity_l": 45, "material": "Heavy Canvas", "shoulder_strap": "Removable"}},

    {"name": "Travis Scott Cactus Jack Bucket Hat", "brand": "Travis Scott", "cat": "accessories", "img": unsplash_accessories[0],
     "desc": "Washed canvas bucket hat embellished with hand-drawn Cactus Jack portrait embroidery.",
     "tags": ["travisscott", "cactusjack", "buckethat", "tan", "festival"],
     "specs": {"color": "Desert Tan", "size": "One Size", "material": "100% Washed Canvas", "brim_width_cm": 6}},

    {"name": "Yeezy Season 6 Bouclé Crew Socks (3-Pack)", "brand": "Yeezy", "cat": "accessories", "img": unsplash_accessories[4],
     "desc": "Thick ribbed cotton blend crew socks in trio of earth tones: Taupe, Graphite, and Trench.",
     "tags": ["yeezy", "socks", "season6", "earthtones", "3pack"],
     "specs": {"colors": "Taupe/Graphite/Trench", "pack_count": 3, "material": "85% Cotton / 13% Polyester / 2% Elastane"}},

    {"name": "Off-White Quote Leather Cardholder", "brand": "Off-White", "cat": "accessories", "img": unsplash_accessories[3],
     "desc": "Smooth matte leather wallet stamped with Virgil Abloh's ironic 'FOR CARDS' quotation print.",
     "tags": ["offwhite", "cardholder", "wallet", "quote", "leather"],
     "specs": {"color": "Black/White", "card_slots": 4, "material": "100% Calfskin Leather", "dimensions_cm": "10x7"}},

    {"name": "Palm Angels Bear Embroidered Baseball Cap", "brand": "Palm Angels", "cat": "accessories", "img": unsplash_accessories[0],
     "desc": "Cotton twill cap featuring the decapitated teddy bear plush applique across the front panel.",
     "tags": ["palmangels", "bearcap", "baseballhat", "black", "streetwear"],
     "specs": {"color": "Black", "size": "Adjustable", "material": "100% Cotton Twill", "applique": "Embroidered Teddy Bear"}},

    {"name": "Supreme Red Box Logo Skateboard Deck", "brand": "Supreme", "cat": "accessories", "img": unsplash_accessories[5],
     "desc": "7-ply North American maple wood skate deck featuring classic full-length red box logo print.",
     "tags": ["supreme", "skatedeck", "boxlogo", "red", "maple", "hardware"],
     "specs": {"color": "Red/White", "width_inches": 8.25, "material": "7-Ply Hardrock Maple", "concave": "Medium"}},

    {"name": "Rhude Rhangelier Silver Chain Necklace", "brand": "Rhude", "cat": "accessories", "img": unsplash_accessories[3],
     "desc": "Sterling silver Cuban link chain featuring custom Rhude crest pendant clasp.",
     "tags": ["rhude", "necklace", "sterlingsilver", "cubanlink", "jewelry"],
     "specs": {"color": "Silver", "length_inches": 20, "material": "925 Sterling Silver", "clasp": "Custom Crest Box Lock"}},

    {"name": "Stüssy Stock Logo Knit Beanie", "brand": "Stüssy", "cat": "accessories", "img": unsplash_accessories[0],
     "desc": "Warm acrylic rib-knit cuff beanie styled with classic white embroidered Stüssy stock logo.",
     "tags": ["stussy", "beanie", "knitcap", "black", "winter"],
     "specs": {"color": "Black", "size": "One Size Fits Most", "material": "100% Acrylic Knit", "cuff": "Folded"}},

    {"name": "Kith Palette 10-Year Anniversary Cap", "brand": "Kith", "cat": "accessories", "img": unsplash_accessories[0],
     "desc": "Structured 6-panel cap crafted from premium suede with subtle tonal anniversary branding.",
     "tags": ["kith", "cap", "suede", "anniversary", "dustyrose"],
     "specs": {"color": "Dusty Rose Suede", "size": "Adjustable Strapback", "material": "100% Goat Suede"}},

    {"name": "Yeezy Gap Snake Bag", "brand": "Yeezy", "cat": "accessories", "img": unsplash_accessories[1],
     "desc": "Tubular seamless nylon body bag designed to be worn across the torso or folded as a tote.",
     "tags": ["yeezy", "gap", "snakebag", "minimalist", "black"],
     "specs": {"color": "Black", "material": "100% Matte Waterproof Nylon", "length_cm": 110, "versatility": "Multi-wear"}},

    {"name": "Fear of God Essentials Leather Tote Bag", "brand": "Fear of God", "cat": "accessories", "img": unsplash_accessories[1],
     "desc": "Minimalist open-top tote bag constructed from smooth calfskin with embossed logo detail.",
     "tags": ["fog", "essentials", "totebag", "leather", "black"],
     "specs": {"color": "Black", "capacity_l": 18, "material": "100% Full-Grain Leather", "handles": "Dual Shoulder"}},

    {"name": "Oakley x Plantaris Futuristic Sunglasses", "brand": "Nike", "cat": "accessories", "img": unsplash_accessories[2],
     "desc": "Biomorphic frame design with removable nose guard and Prizm high-definition optics.",
     "tags": ["oakley", "futuristic", "plantaris", "sunglasses", "gorpcore"],
     "specs": {"color": "Matte Sand/Prizm Tungsten", "lens_technology": "Prizm Optics", "uv_rating": "UV400"}},

    {"name": "Heron Preston Tape Belt 'Orange'", "brand": "Heron Preston", "cat": "accessories", "img": unsplash_accessories[0],
     "desc": "High-visibility orange jacquard logo tape belt with industrial slide buckle fastening.",
     "tags": ["heronpreston", "belt", "orange", "tapebelt", "workwear"],
     "specs": {"color": "Industrial Orange", "length_cm": 125, "material": "Polyamide/Polyester", "buckle": "Slide Clamp"}},

    {"name": "Vetements 'Security' Keychain Lanyard", "brand": "Vetements", "cat": "accessories", "img": unsplash_accessories[0],
     "desc": "Heavy duty lanyard strap woven with yellow security lettering and heavy metal carabiner hook.",
     "tags": ["vetements", "lanyard", "keychain", "security", "yellow"],
     "specs": {"color": "Safety Yellow/Black", "length_cm": 50, "material": "Nylon Webbing", "attachment": "Steel Carabiner"}},

    {"name": "Supreme Zippo Armor Case Lighter 'Gold'", "brand": "Supreme", "cat": "accessories", "img": unsplash_accessories[3],
     "desc": "Brass windproof Zippo lighter styled with deep engraved Supreme repeating pattern.",
     "tags": ["supreme", "zippo", "lighter", "gold", "brass", "accessory"],
     "specs": {"color": "Brass Gold", "material": "Solid Brass", "fuel_type": "Zippo Lighter Fluid (Not Included)"}}
]

# Ensure we expand definitions dynamically to hit EXACTLY 75 unique items with distinct product IDs!
# Let's generate 75 distinct items with specific unique IDs (prod_01 ... prod_75)

all_products = []

# Base template list length is 75 (30 + 25 + 20 = 75!)
assert len(product_definitions) == 75, f"Expected 75 product definitions, got {len(product_definitions)}"

# Assign unique IDs from prod_01 to prod_75
id_list = [f"prod_{i+1:02d}" for i in range(75)]

for idx, item in enumerate(product_definitions):
    prod_id = id_list[idx]
    
    # Generate related product IDs (pick 3-4 other IDs from id_list distinct from current)
    other_ids = [pid for pid in id_list if pid != prod_id]
    # Pick deterministic or seed-based random to ensure reproducibility
    random.seed(idx * 42)
    related_selected = random.sample(other_ids, k=3)
    related_str = ",".join(related_selected) # comma-separated string, no spaces after commas
    
    tags_str = ",".join(item["tags"]) # comma-separated string, no spaces after commas
    
    # Calculate realistic INR price (Streetwear luxury market pricing)
    # Sneakers: 12,000 to 1,45,000 INR
    # Apparel: 8,500 to 85,000 INR
    # Accessories: 4,500 to 65,000 INR
    if item["cat"] == "sneakers":
        price = random.choice([14500, 18000, 22000, 26500, 32000, 45000, 68000, 95000, 120000])
    elif item["cat"] == "apparel":
        price = random.choice([8500, 12500, 16500, 24000, 35000, 48000, 62000, 78000])
    else:
        price = random.choice([4500, 7500, 11500, 15000, 21000, 28000, 39000, 52000])
        
    stock = random.randint(3, 40)
    
    product_obj = {
        "id": prod_id,
        "name": item["name"],
        "brand": item["brand"],
        "category": item["cat"],
        "price_inr": price,
        "stock": stock,
        "description": item["desc"],
        "specs": item["specs"],
        "tags": tags_str,
        "related": related_str,
        "image_url": item["img"]
    }
    all_products.append(product_obj)

# Validation check
assert len(all_products) == 75
unique_ids = set(p["id"] for p in all_products)
assert len(unique_ids) == 75

for p in all_products:
    assert isinstance(p["specs"], dict), f"specs for {p['id']} is not a dict!"
    assert " " not in p["tags"].replace(",", ""), "spaces found in tags string!" # simple check
    for r in p["related"].split(","):
        assert r in unique_ids, f"related ID {r} not in generated product IDs!"

# Print out JSON formatted string
json_output = json.dumps(all_products, indent=2)
print(f"Generated {len(all_products)} products successfully.")

# Write to local file
with open("catalog.json", "w") as f:
    f.write(json_output)
