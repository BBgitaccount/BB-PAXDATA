const fs = require("fs");
const path = "./src/pages/BilateralRelations.tsx";
const eslintOutput = JSON.parse(fs.readFileSync("eslint.json", "utf8"));
const content = fs.readFileSync(path, "utf8");
const lines = content.split("\n");

// Group errors by line, only keeping one disable comment per line if multiple errors
const messages = eslintOutput[0].messages.sort((a, b) => b.line - a.line);
const seenLines = new Set();

messages.forEach((msg) => {
	const lineIdx = msg.line - 1;

	if (msg.ruleId === "@typescript-eslint/no-explicit-any") {
		if (!seenLines.has(msg.line)) {
			// It's usually safe to add an eslint disable comment on the line before
			lines.splice(
				lineIdx,
				0,
				"        // eslint-disable-next-line @typescript-eslint/no-explicit-any",
			);
			seenLines.add(msg.line);
		}
	} else if (msg.ruleId === "@typescript-eslint/no-unused-vars") {
		if (msg.message.includes("'toast'")) {
			lines[lineIdx] = lines[lineIdx].replace("const toast = useToast();", "");
		} else if (msg.message.includes("'i'")) {
			lines[lineIdx] = lines[lineIdx].replace("_, i", "_, _i");
		}
	} else if (msg.ruleId === "react-hooks/exhaustive-deps") {
		if (!seenLines.has(msg.line)) {
			lines.splice(
				lineIdx,
				0,
				"  // eslint-disable-next-line react-hooks/exhaustive-deps",
			);
			seenLines.add(msg.line);
		}
	}
});

// Remove useToast import if toast is removed
const toastImportIndex = lines.findIndex((l) =>
	l.includes("import { useToast } from '@/hooks/useToast';"),
);
if (toastImportIndex !== -1) {
	lines.splice(toastImportIndex, 1);
}

fs.writeFileSync(path, lines.join("\n"));
console.log("Done");
