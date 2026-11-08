
import "dotenv/config";
import { Files } from "files-sdk";
import { neon } from "files-sdk/neon";

const files = new Files({
  adapter: neon({ bucket: "uploads" }),
});

const key = "verification/test.txt";
const originalText = "Hello! Neon private Object Storage upload test successful.";

async function main() {
  // 1. Upload
  await files.upload(key, originalText, {
    contentType: "text/plain",
  });
  console.log("SUCCESS: File uploaded.");

  // 2. List bucket objects
  const listing = await files.list({
    prefix: "verification/",
  });

  console.log("\nBUCKET LIST:");
  console.log(JSON.stringify(listing, null, 2));

  // 3. Download
  const downloaded = await files.download(key);
  const downloadedText = await downloaded.text();

  console.log("\nDOWNLOADED FILE CONTENT:");
  console.log(downloadedText);

  // 4. Verify
  if (downloadedText !== originalText) {
    throw new Error("Downloaded content does not match!");
  }

  console.log("\nSUCCESS: Upload, listing and download verified!");
}

main().catch((error) => {
  console.error("TEST FAILED:", error.message);
  process.exitCode = 1;
});
