const yargs = require("yargs");
const fs = require("fs");
const fastCsv = require("fast-csv");
const { format } = require('@fast-csv/format');
const path = require("path");
const {
  getParsedUSFM,
  getTargetQuoteFromSourceQuote,
} = require("uw-quote-helpers");

const addGLQuotesToTSV = (sourcePath, targetPath, tnPath) => {
  console.time("getTranslationNotes()");
  console.time("getting resources");
  console.time("fetching resources");

  const sourceUsfm = fs.readFileSync(
    sourcePath,
    "utf8"
  );
  const sourceBook = getParsedUSFM(sourceUsfm).chapters;

  const targetUsfm = fs.readFileSync(
    targetPath,
    "utf8"
  );
  const targetBook = getParsedUSFM(targetUsfm).chapters;

  console.timeEnd("fetching resources");
  console.time("getting resources");

  console.time("getting notes");

  const tsvOptions = {
    objectMode: true,
    quote: '"',
    delimiter: "\t",
    headers: true,
  };
  let rows = [];

  fs.createReadStream(tnPath)
    .pipe(fastCsv.parse(tsvOptions))
    .on("data", function (row) {
      const quote = row["OrigQuote"];
      const ref = row["Chapter"] + ":" + row["Verse"];
      const occurrence = row["Occurrence"];
      const params = {
        quote,
        ref,
        sourceBook,
        targetBook,
        options: { occurrence, fromOrigLang: true },
      };
      console.log("BEFORE LOOKUP: ", [row["Book"] + " " +ref, quote, occurrence].join(', '));

      if (quote && occurrence && occurrence != "0") {
        // console.log(`Generating target quote matching source quote`);
        try {
          const glQuote = getTargetQuoteFromSourceQuote(params);
          // console.log({ glQuote });
          row["GLQuote"] = glQuote;
          if (!row["GLQuote"]) {
            row["GLQuote"] = "";
          }
        } catch (e) {
					console.log(e);
					exit(1);
          row["GLQuote"] = "";
        }
      } else {
        row["GLQuote"] = "";
      }
      console.log("AFTER LOOKUP: ", [row["Book"] + " " +ref, quote, row["GLQuote"]].join(', '));
      rows.push(row);
    })
    .on("end", function () {
      console.log("ENDED!!!!");
			console.timeEnd("getting notes");
			const tnFile = fs.createWriteStream(tnPath+".new", {flags: 'w', encoding: "utf-8"});
			const stream = format(tsvOptions);
			stream.pipe(tnFile)
			rows.forEach(row => {
				console.log("WRITING ROW: "+row["Book"]+" "+row["Chapter"]+":"+row["Verse"]+": "+row["GLQuote"]);
				stream.write(row);
			});
			stream.end();
		});
};

const args = yargs.argv;

const sourcePath = args.source_path
const targetPath = args.target_path
const tnPath = args.tn_path

if (! sourcePath) {
  throw Error('souce_path cannot be empty');
}
if (! targetPath) {
  throw Error('target_path cannot be empty');
}
if (! tnPath) {
  throw Error('tn_path cannot be empty');
}
if (!fs.existsSync(sourcePath)) {
  throw Error('source_path does not exist: ' + sourcePath);
}
if (!fs.existsSync(targetPath)) {
  throw Error('target_path does not exist: ' + targetPath);
}
if (!fs.existsSync(tnPath)) {
  throw Error('tn_path does not exist: ' + tnPath);
}

addGLQuotesToTSV(sourcePath, targetPath, tnPath);
