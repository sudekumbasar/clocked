// Checks the public build has no test mode (PRODUCT.md, "Testing without being there"):
// no saved-photo picker, no "Pretend I am here", no reset. Run after `npm run build`.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const FORBIDDEN = ["Pretend I am here", "Saved photo", "Test mode", "resetCollection", "TestTools"];
const dir = new URL("../dist/assets/", import.meta.url).pathname;
const found = [];
for (const file of readdirSync(dir)) {
  if (!file.endsWith(".js")) continue;
  const text = readFileSync(join(dir, file), "utf8");
  for (const word of FORBIDDEN) if (text.includes(word)) found.push(`${file}: ${word}`);
}
if (found.length) {
  console.error("The public build contains test-mode code:\n  " + found.join("\n  "));
  process.exit(1);
}
console.log("Public build has no test mode.");
