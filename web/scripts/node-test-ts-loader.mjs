import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import ts from "typescript";

const projectRoot = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const srcRoot = path.join(projectRoot, "src");
const extensions = [".ts", ".tsx", ".js", ".mjs", ".cjs"];

function resolveWithExtensions(basePath) {
  const candidates = [
    basePath,
    ...extensions.map((ext) => `${basePath}${ext}`),
    ...extensions.map((ext) => path.join(basePath, `index${ext}`)),
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
      return candidate;
    }
  }

  return null;
}

export async function resolve(specifier, context, defaultResolve) {
  if (specifier.startsWith("@/")) {
    const candidate = resolveWithExtensions(path.join(srcRoot, specifier.slice(2)));
    if (candidate) {
      return { url: pathToFileURL(candidate).href, shortCircuit: true };
    }
  }

  try {
    return await defaultResolve(specifier, context, defaultResolve);
  } catch (error) {
    if (
      error?.code === "ERR_MODULE_NOT_FOUND" &&
      /^next\//.test(specifier) &&
      !specifier.endsWith(".js")
    ) {
      return defaultResolve(`${specifier}.js`, context, defaultResolve);
    }
    throw error;
  }
}

export async function load(url, context, defaultLoad) {
  if (url.startsWith("file://") && /\.tsx?$/i.test(url)) {
    const filename = fileURLToPath(url);
    const sourceText = fs.readFileSync(filename, "utf8");
    const transpiled = ts.transpileModule(sourceText, {
      compilerOptions: {
        module: ts.ModuleKind.ESNext,
        target: ts.ScriptTarget.ES2022,
        jsx: ts.JsxEmit.ReactJSX,
        esModuleInterop: true,
        isolatedModules: true,
      },
      fileName: filename,
      reportDiagnostics: false,
    });

    return {
      format: "module",
      source: transpiled.outputText,
      shortCircuit: true,
    };
  }

  return defaultLoad(url, context, defaultLoad);
}
