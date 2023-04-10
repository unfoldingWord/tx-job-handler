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
  let rows = [];

  //Fetching resources (Orignal USFM, GL USM)
  const sourceUsfm = fs.readFileSync(
    sourcePath,
    "utf8"
  );
  const targetUsfm = fs.readFileSync(
    targetPath,
    "utf8"
  );

  //Parsing source/original and target/gl books
  const sourceBook = getParsedUSFM(sourceUsfm).chapters;
  const targetBook = getParsedUSFM(targetUsfm).chapters;

  const options = {
    objectMode: true,
    quote: '"',
    delimiter: '\t',
    headers: true,
  };

  fs.createReadStream(tnPath)
  .pipe(fastCsv.parse(options))
  .on("data", function(row) {
    //Getting the target quote as a string from a source quote string.
    const quote = row["OrigQuote"];
    const ref = row["Chapter"]+":"+row["Verse"];
    const occurrence = row["Occurrence"];

    if (quote) {
      // console.log(`Generating target quote matching source quote: "${sourceQuote}", in: ${row[0]} "${reference}" `);
      try {
        row["GLQuote"] = getTargetQuoteFromSourceQuote({
          quote,
          ref,
          sourceBook,
          targetBook,
          options: { occurrence, fromOrigLang: true },
        });
        if (! row["GLQuote"]) {
          row["GLQuote"] = "";
        }
      } catch(e) {
        row["GLQuote"] = "";
      }
    } else {
      row["GLQuote"] = "";
    }
    rows.push(row);
  })
  .on("end", function() {
    const tnFile = fs.createWriteStream(tnPath, {flags: 'w'});
    const stream = format(options);
    stream.pipe(tnFile)
    rows.forEach(row => {
      stream.write(row);
    });
    stream.end();
  })
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
