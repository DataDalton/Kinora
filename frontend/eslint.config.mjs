import nextPlugin from "@next/eslint-plugin-next";
import reactHooks from "eslint-plugin-react-hooks";
import babelParser from "@babel/eslint-parser";

// Babel parses TypeScript syntax without loading the TypeScript compiler API.
// typescript-eslint cannot be used here because it throws on TypeScript 7.
// Parser plugins are set directly because @babel/eslint-parser reads
// babelOptions.parserOpts.plugins and ignores presets.
const babelParserOptions = (plugins) => ({
	requireConfigFile: false,
	babelOptions: {
		babelrc: false,
		configFile: false,
		parserOpts: { plugins },
	},
});

export default [
	{
		ignores: [".next/**", "out/**", "build/**", "next-env.d.ts"],
	},
	{
		// Plain .ts files exclude the jsx plugin so angle bracket type assertions parse.
		files: ["**/*.ts"],
		languageOptions: {
			parser: babelParser,
			ecmaVersion: "latest",
			sourceType: "module",
			parserOptions: babelParserOptions(["typescript"]),
		},
	},
	{
		files: ["**/*.{tsx,js,jsx,mjs,cjs}"],
		languageOptions: {
			parser: babelParser,
			ecmaVersion: "latest",
			sourceType: "module",
			parserOptions: babelParserOptions(["typescript", "jsx"]),
		},
	},
	{
		files: ["**/*.{ts,tsx,js,jsx,mjs,cjs}"],
		plugins: {
			"@next/next": nextPlugin,
			"react-hooks": reactHooks,
		},
		rules: {
			...nextPlugin.configs.recommended.rules,
			...nextPlugin.configs["core-web-vitals"].rules,
			...reactHooks.configs["recommended-latest"].rules,
		},
	},
];
