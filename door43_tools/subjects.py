ALIGNED_BIBLE = "Aligned Bible"
BIBLE = "Bible"
GREEK_NEW_TESTAMENT = "Greek New Testament"
HEBREW_OLD_TESTAMENT = "Hebrew Old Testament"
OBS_STUDY_NOTES = "OBS Study Notes"
OBS_STUDY_QUESTIONS = "OBS Study Questions"
OBS_TRANSLATION_NOTES = "OBS Translation Notes"
OBS_TRANSLATION_QUESTIONS = "OBS Translation Questions"
OPEN_BIBLE_STORIES = "Open Bible Stories"
STUDY_NOTES = "Study Notes"
STUDY_QUESTIONS = "Study Questions"
TRANSLATION_ACADEMY = "Translation Academy"
TRANSLATION_NOTES = "Translation Notes"
TRANSLATION_QUESTIONS = "Translation Questions"
TRANSLATION_WORDS = "Translation Words"
TSV_STUDY_NOTES = "TSV Study Notes"
TSV_STUDY_QUESTIONS = "TSV Study Questions"
TSV_TRANSLATION_NOTES = "TSV Translation Notes"

SUBJECT_ALIASES = {
  ALIGNED_BIBLE: ['ult', 'ust', ALIGNED_BIBLE, ALIGNED_BIBLE.replace(" ", "_")],
  BIBLE: ['ult', 'ust', BIBLE, BIBLE.replace(" ", "_"), 'usfm', 'bible'],
  GREEK_NEW_TESTAMENT: ["ugnt", GREEK_NEW_TESTAMENT, GREEK_NEW_TESTAMENT.replace(" ", "_")],
  HEBREW_OLD_TESTAMENT: ["uhb", HEBREW_OLD_TESTAMENT, HEBREW_OLD_TESTAMENT.replace(" ", "_")],
  OBS_STUDY_NOTES: ["obs-sn", OBS_STUDY_NOTES, OBS_STUDY_NOTES.replace(" ", "_"), "Open Bible Study Notes"],
  OBS_STUDY_QUESTIONS: ["obs-sq", OBS_STUDY_QUESTIONS, OBS_STUDY_QUESTIONS.replace(" ", "_"), "Open Bible Study Questions"],
  OBS_TRANSLATION_NOTES: ["obs-tn", OBS_TRANSLATION_NOTES, OBS_TRANSLATION_NOTES.replace(" ", "_"), "Open Bible Translation Notes"],
  OBS_TRANSLATION_QUESTIONS: ["obs-tq", OBS_TRANSLATION_QUESTIONS, OBS_TRANSLATION_QUESTIONS.replace(" ", "_"), "Open Bible Translation Questions"],
  OPEN_BIBLE_STORIES: ["obs", OPEN_BIBLE_STORIES, OPEN_BIBLE_STORIES.replace(" ", "_")],
  STUDY_NOTES: [STUDY_NOTES, STUDY_NOTES.replace(" ", "_")],
  STUDY_QUESTIONS: [STUDY_QUESTIONS, STUDY_QUESTIONS.replace(" ", "_")],
  TRANSLATION_ACADEMY: ["ta", TRANSLATION_ACADEMY, TRANSLATION_ACADEMY.replace(" ", "_")],
  TRANSLATION_NOTES: [TRANSLATION_NOTES, TRANSLATION_NOTES.replace(" ", "_")],
  TRANSLATION_QUESTIONS: ["tq", TRANSLATION_QUESTIONS, TRANSLATION_QUESTIONS.replace(" ", "_")],
  TRANSLATION_WORDS: ["tw", TRANSLATION_WORDS, TRANSLATION_WORDS.replace(" ", "_")],
  TSV_TRANSLATION_NOTES: ["tn", TSV_TRANSLATION_NOTES, TSV_TRANSLATION_NOTES.replace(" ", "_")],
  TSV_STUDY_NOTES: ["sn", TSV_STUDY_NOTES, TSV_STUDY_NOTES.replace(" ", "_")],
  TSV_STUDY_QUESTIONS: ["sq", TSV_STUDY_QUESTIONS, TSV_STUDY_QUESTIONS.replace(" ", "_")],
}

# Resources (right) that are referenced or to be used by the given resource (left) for generating printable material
REQUIRED_RESOURCES = {
    ALIGNED_BIBLE: [HEBREW_OLD_TESTAMENT, GREEK_NEW_TESTAMENT],
    BIBLE: [],
    GREEK_NEW_TESTAMENT: [],
    HEBREW_OLD_TESTAMENT: [],
    OBS_STUDY_NOTES: [OBS_STUDY_QUESTIONS, OPEN_BIBLE_STORIES],
    OBS_STUDY_QUESTIONS: [OPEN_BIBLE_STORIES],
    OBS_TRANSLATION_NOTES: [OPEN_BIBLE_STORIES, TRANSLATION_ACADEMY, TRANSLATION_WORDS],
    OBS_TRANSLATION_QUESTIONS: [OPEN_BIBLE_STORIES],
    OPEN_BIBLE_STORIES: [],
    STUDY_NOTES: [ALIGNED_BIBLE, STUDY_QUESTIONS],
    STUDY_QUESTIONS: [BIBLE],
    TRANSLATION_ACADEMY: [TRANSLATION_WORDS],
    TRANSLATION_NOTES: [ALIGNED_BIBLE, ALIGNED_BIBLE, HEBREW_OLD_TESTAMENT, GREEK_NEW_TESTAMENT, TRANSLATION_ACADEMY,
                        TRANSLATION_WORDS],
    TRANSLATION_QUESTIONS: [BIBLE],
    TRANSLATION_WORDS: [TRANSLATION_ACADEMY],
    TSV_TRANSLATION_NOTES: [ALIGNED_BIBLE, ALIGNED_BIBLE, HEBREW_OLD_TESTAMENT, GREEK_NEW_TESTAMENT, TRANSLATION_ACADEMY,
                            TRANSLATION_WORDS],
    TSV_STUDY_NOTES: [ALIGNED_BIBLE, ALIGNED_BIBLE, HEBREW_OLD_TESTAMENT, GREEK_NEW_TESTAMENT, TSV_STUDY_QUESTIONS],
    TSV_STUDY_QUESTIONS: [ALIGNED_BIBLE, ALIGNED_BIBLE, HEBREW_OLD_TESTAMENT, GREEK_NEW_TESTAMENT],
}
