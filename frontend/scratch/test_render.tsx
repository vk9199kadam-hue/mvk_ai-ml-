import React from "react";
import ReactDOMServer from "react-dom/server";
import RootLayout from "../src/app/layout";

try {
  console.log("Starting RootLayout render test...");
  const html = ReactDOMServer.renderToString(
    <RootLayout>
      <div>Test Child</div>
    </RootLayout>
  );
  console.log("Render succeeded! HTML length:", html.length);
} catch (error) {
  console.error("Render failed with error:", error);
}
