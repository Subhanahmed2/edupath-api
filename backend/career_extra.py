"""
Extra curated data for the career/program stage.

  RULES   : minimum intermediate marks per program WITH ITS SOURCE (sourced 2026-10-23, see
            reports/verification_log.md). Policy: where a regulator sets the rule (PM&DC, PEC, NCEAC/HEC,
            PCP, PNMC) its figure is used; where only universities set it, the LOWEST minimum found on an
            official university page is used, so the tool never wrongly rules a student out - many
            universities ask more. "verified" stays empty until a team member checks the source.
  SKILLS  : 4 core skills per career for the skill-gap check (curated guidance, not verified - review
            with your supervisor), each with a tip and optional questionnaire evidence that pre-ticks it.
"""
from career_bank import BANK, PROGRAMS

SRC = {
    "pmdc": ("regulator", "PM&DC Medical and Dental Undergraduate Education (Admissions, Curriculum and Conduct) "
             "Policy and Regulations 2025, Reg. 3(1): MDCAT passed, HSSC >= 60%, Biology and Chemistry compulsory",
             "https://www.pmdc.pk/Documents/Others/Admissions%20Regulations-2025.pdf"),
    "pec": ("regulator", "PEC Regulations for Engineering Education (amended to SRO 1606(I)/2021), Art. 2: HSSC "
            "Pre-Engineering >= 60% + entrance test; Physics+Maths+Computer Science allowed only for computer-related, "
            "electronics, telecom and avionics engineering",
            "https://www.pec.org.pk/wp-content/uploads/2022/11/REGULATIONS-FOR-ENGG-EDU.pdf"),
    "nceac": ("regulator", "NCEAC/HEC admission criteria for BS Computing: >= 50% with Mathematics; without "
              "Mathematics, 6 credits of deficiency Mathematics in the first year",
              "https://nceac.org.pk/Documents/Alerts/AlertDocuments/Admission%20Criteria.pdf"),
    "pcp": ("regulator", "Pharmacy Council of Pakistan: Pharm-D requires F.Sc Pre-Medical or equivalent >= 60%",
            "https://pcpisb.gov.pk/"),
    "pnmc": ("regulator", "Pakistan Nursing & Midwifery Council: Generic BSN requires F.Sc Pre-Medical >= 50% "
             "(Physics, Chemistry, Biology)", "https://pnmc.gov.pk/admission-criteria/"),
    "uet": ("university", "UET Lahore admissions: 60% in intermediate for Engineering and Architecture (university-set)",
            "https://admission.uet.edu.pk/program/1"),
    "riphah": ("university", "Riphah International University DPT: minimum 60% in intermediate with pre-medical "
               "subjects (university-set; others ask 60-70%)", "https://riphah.edu.pk/programs/detail/?p=68"),
    "uoh": ("university", "University of Haripur eligibility: 45% for MLT and Human Nutrition (university-set; "
            "other universities ask 50-60%)", "https://www.uoh.edu.pk/admissions/eligibility"),
    "umt_llb": ("university", "UMT LLB: intermediate >= 45% plus the HEC Law Admission Test (LAT); some universities "
                "ask 50-55%", "https://slp.umt.edu.pk/programs/llb.aspx"),
    "typical": ("typical", "Typical university minimum for BS programs (45%). HEC sets no general first-year minimum; "
                "each university sets its own", None),
}
RULES = {  # program -> (minimum %, source key)
    "mbbs": (60, "pmdc"), "bds": (60, "pmdc"), "pharmd": (60, "pcp"), "bsn": (50, "pnmc"),
    "dpt": (60, "riphah"), "mlt": (45, "uoh"), "nutrition": (45, "uoh"),
    "ee": (60, "pec"), "me": (60, "pec"), "ce": (60, "pec"), "che": (60, "pec"), "mte": (60, "pec"),
    "arch": (60, "uet"),
    "bscs": (50, "nceac"), "bsse": (50, "nceac"), "bsai": (50, "nceac"), "bsds": (50, "nceac"),
    "bscyber": (50, "nceac"), "bsit": (50, "nceac"),
    "llb": (45, "umt_llb"),
}
RULES_SOURCED = "2026-10-23"
for _pid, _p in PROGRAMS.items():
    _pct, _key = RULES.get(_pid, (45, "typical"))
    _basis, _text, _url = SRC[_key]
    _p.update(min_pct=_pct, rule_basis=_basis, rule_source=_text, rule_url=_url,
              rule_sourced=RULES_SOURCED, rule_verified=None)  # verified: set after a team member checks


def S(name, tip, **evidence):
    return {"name": name, "tip": tip, "evidence": evidence}


_AGREE = ["Strongly agree", "Agree"]
MATHS = S("Maths", "Practise past papers and a free online calculus/statistics course.",
          math_confident=_AGREE, math_person=_AGREE)
SCIENCE = S("Science foundations", "Revise intermediate physics, chemistry and biology concepts.", science_person=_AGREE)
BIOLOGY = S("Biology", "Strengthen anatomy and physiology basics; MDCAT preparation books help.", fav_subject=["Biology"])
CHEM = S("Chemistry", "Revise organic, inorganic and physical chemistry.", fav_subject=["Chemistry"])
COMMS = S("Communication", "Join a debate or presentation club; practise explaining topics to others.")
PROGRAMMING = S("Programming", "Start with Python - build one small project every week.", fav_subject=["Computer Science"])
ENGLISH = S("English reading & writing", "Read one long article a day and write a short summary.", fav_subject=["English"])
STATS = S("Statistics & probability", "Take a free introductory statistics course.")
SHEETS = S("Spreadsheets", "Analyse a small dataset or budget in Excel or Google Sheets.")
DETAIL = S("Attention to detail", "Practise careful, step-by-step work and double-check your answers.")
TEAM = S("Teamwork", "Join group projects, clubs or volunteering teams.")
CALM = S("Calm under pressure", "Take a first-aid course (e.g. Red Crescent) or volunteer at a hospital.")
LAB = S("Lab techniques", "Do extra practicals carefully; learn to use a microscope well.")
CREATIVE = S("Creativity", "Keep a scrapbook of designs and ideas you like and try your own versions.")
DRAW = S("Drawing & sketching", "Sketch something every day.")
NEWS = S("Current affairs", "Follow national and international news every day.")
DEBATE = S("Debating & public speaking", "Join a debating society or Model United Nations.")
NETWORK = S("Networking basics", "Learn how the internet works: IP addresses, DNS, routers, HTTP.")
EMPATHY = S("Listening & empathy", "Volunteer with a welfare organisation or peer-support group.")
ELECTRONICS = S("Electronics tinkering", "Build simple circuits or a small robot with an Arduino kit.")
MECHANICS = S("Physics (mechanics)", "Revise forces, motion and energy; solve extra problems.", fav_subject=["Physics"])

SKILLS = {
    # Medical & Health
    "doctor": [BIOLOGY, S("Long-term study discipline", "Plan a weekly study timetable for MDCAT and keep to it."), CALM, COMMS],
    "dentist": [BIOLOGY, S("Fine hand skills", "Try drawing, model making or any precise craft."), DETAIL, COMMS],
    "pharmacist": [CHEM, BIOLOGY, DETAIL, COMMS],
    "physio": [BIOLOGY, S("Fitness & human movement", "Play a sport and learn basic exercise science."), EMPATHY, COMMS],
    "nurse": [BIOLOGY, TEAM, CALM, EMPATHY],
    "lab": [BIOLOGY, LAB, DETAIL, CHEM],
    "nutritionist": [BIOLOGY, CHEM, COMMS, S("Interest in food & health", "Track your own diet for a week and read nutrition labels.")],
    # Engineering & Tech
    "electrical": [MATHS, S("Physics (electricity & magnetism)", "Revise circuits and electromagnetism chapters.", fav_subject=["Physics"]), ELECTRONICS, PROGRAMMING],
    "mechanical": [MATHS, MECHANICS, S("Hands-on building", "Repair or build something mechanical; try a free CAD tutorial."), S("Problem solving", "Solve one challenging physics problem set a week.")],
    "civil": [MATHS, MECHANICS, S("Technical drawing / CAD", "Learn basic AutoCAD from free tutorials."), TEAM],
    "chemical": [MATHS, CHEM, S("Problem solving", "Practise numerical chemistry and physics problems."), S("Safety mindset", "Read about lab and industrial safety rules.")],
    "mechatronics": [MATHS, PROGRAMMING, ELECTRONICS, MECHANICS],
    "architect": [DRAW, CREATIVE, MATHS, S("3D / CAD software", "Try SketchUp or Blender with free tutorials.")],
    # CS & IT
    "software": [PROGRAMMING, S("Problem solving", "Solve beginner problems on a coding practice website."), TEAM, MATHS],
    "web_mobile": [PROGRAMMING, S("Web basics (HTML, CSS, JavaScript)", "Build your own personal website."), S("Design sense", "Recreate the layout of an app you like."), TEAM],
    "ai": [MATHS, PROGRAMMING, STATS, S("Research curiosity", "Read one AI article a week and summarise it.")],
    "data": [MATHS, STATS, PROGRAMMING, SHEETS],
    "cyber": [PROGRAMMING, NETWORK, S("Puzzle solving", "Try beginner capture-the-flag (CTF) challenges."), S("Ethics & responsibility", "Learn where ethical hacking ends and illegal hacking begins.")],
    "network": [NETWORK, S("Troubleshooting", "Fix computer problems for family and friends."), PROGRAMMING, S("Linux basics", "Install Linux in a virtual machine and learn basic commands.")],
    # Business
    "accountant": [MATHS, SHEETS, DETAIL, ENGLISH],
    "finance": [MATHS, SHEETS, S("Interest in markets", "Follow the stock exchange and business news weekly."), COMMS],
    "marketing": [COMMS, CREATIVE, S("Understanding people", "Ask friends why they buy what they buy."), ENGLISH],
    "entrepreneur": [S("Leadership", "Lead a club, event or small team project."), COMMS, S("Resilience", "Start a small online project and learn from what goes wrong."), S("Money basics", "Track the costs and profit of a small sale or event.")],
    "hr": [COMMS, EMPATHY, S("Organisation", "Plan and run an event from start to finish."), ENGLISH],
    "analyst": [MATHS, SHEETS, STATS, COMMS],
    # Natural Sciences
    "biotech": [BIOLOGY, CHEM, LAB, S("Research curiosity", "Read popular science articles on genetics.")],
    "microbiologist": [BIOLOGY, LAB, DETAIL, CHEM],
    "chemist": [CHEM, LAB, MATHS, S("Safety mindset", "Learn and follow lab safety rules.")],
    "physicist": [MATHS, S("Physics", "Solve physics problems beyond the syllabus.", fav_subject=["Physics"]), S("Problem solving", "Try physics olympiad-style questions."), PROGRAMMING],
    "mathematician": [MATHS, S("Logical proofs", "Work through a beginner's book or course on proofs."), S("Problem solving", "Try maths olympiad problems."), PROGRAMMING],
    "environmental": [SCIENCE, S("Fieldwork & observation", "Join a tree-planting or clean-up campaign and record what you see."), S("Report writing", "Write a short report on a local environmental issue."), S("Maps & data (GIS)", "Explore Google Earth and simple map data.")],
    # Social Sci / Law / Psych
    "lawyer": [ENGLISH, DEBATE, S("Logical reasoning", "Practise LAT-style reasoning questions."), S("Reading stamina", "Read a long newspaper editorial every day.")],
    "psychologist": [EMPATHY, S("Curiosity about people", "Read an introductory psychology book."), ENGLISH, S("Research basics", "Learn how surveys and experiments are designed.")],
    "economist": [MATHS, STATS, S("Following the economy", "Read business news and State Bank updates."), ENGLISH],
    "diplomat": [ENGLISH, NEWS, DEBATE, S("Languages", "Start learning a foreign language with an app.")],
    "civil_servant": [ENGLISH, NEWS, S("General knowledge", "Practise CSS-style general knowledge questions."), COMMS],
    "social_worker": [EMPATHY, COMMS, S("Community organising", "Help organise a community event."), ENGLISH],
    # Education / Humanities / Arts
    "teacher": [COMMS, S("Patience", "Tutor younger students or siblings regularly."), S("Subject knowledge", "Master one subject you would like to teach."), S("Planning", "Plan a short lesson and teach it to friends.")],
    "journalist": [ENGLISH, S("Writing to deadlines", "Write a short news story every week."), S("Interviewing", "Interview people about a local issue."), S("Photo & video basics", "Shoot and edit short reports on your phone.")],
    "designer": [DRAW, S("Design software", "Learn Canva, then Figma or Photoshop from free tutorials."), CREATIVE, S("Portfolio", "Collect your 10 best designs in one place.")],
    "writer": [ENGLISH, S("Regular writing", "Write 300 words every day - stories, blogs or poems."), S("Reading widely", "Read one book a month in different genres."), S("Editing", "Rewrite and improve something you wrote last week.")],
    "filmmaker": [S("Video shooting & editing", "Make short films on your phone and edit them with free software."), S("Storytelling", "Write short scripts or storyboards."), CREATIVE, TEAM],
    "linguist": [ENGLISH, S("Second language", "Start learning another language with an app."), S("Urdu reading & writing", "Read Urdu literature and write short pieces.", fav_subject=["Urdu"]), S("Translation practice", "Translate short articles between Urdu and English.")],
}

_all = [c for b in BANK.values() for c in b["careers"]]
assert set(SKILLS) == set(_all), f"SKILLS out of sync: missing {set(_all) - set(SKILLS)}, extra {set(SKILLS) - set(_all)}"


def skill_gap(career_id, profile=None):
    """Skills for a career; 'suggested' = pre-ticked because the student's questionnaire answers show it."""
    profile = profile or {}
    out = []
    for s in SKILLS.get(career_id, []):
        hit = next((f"{q}: {profile[q]}" for q, ok in s["evidence"].items() if profile.get(q) in ok), None)
        out.append({"name": s["name"], "tip": s["tip"], "suggested": bool(hit), "evidence": hit})
    return out
