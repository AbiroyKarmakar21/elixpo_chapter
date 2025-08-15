import { readTemplateStructureFromJson, saveTemplateStructureToJson } from "@/features/playground/lib/path-to-json";
import prisma from "@/lib/db";
import path from "path";
import fs from 'fs/promises'
import { NextRequest } from "next/server";
import { templatePaths } from "@/lib/template";

function validateJson(data: unknown): boolean {
  if (typeof data !== 'object' || data === null) {
    return false;
  }
  return true;
}

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = params;
    
    if (!id) {
      return Response.json({ error: "Missing PlayGround Id" }, { status: 400 });
    }

    const playground = await prisma.playground.findUnique({
      where: { id }
    });

    if (!playground) {
      return Response.json({ error: "PlayGround not found" }, { status: 404 });
    }

    if (!playground.template || !(playground.template in templatePaths)) {
      return Response.json({ error: "Invalid template specified" }, { status: 400 });
    }

    const templateKey = playground.template as keyof typeof templatePaths;
    const templatePath = templatePaths[templateKey];
    const inputPath = path.join(process.cwd(), templatePath);
    const outputFile = path.join(process.cwd(), `output/${templateKey}.json`);

    try {
      // Create output directory if it doesn't exist
      await fs.mkdir(path.dirname(outputFile), { recursive: true });
      
      await saveTemplateStructureToJson(inputPath, outputFile);
      const templateData = await readTemplateStructureFromJson(outputFile);

      if (!validateJson(templateData?.items)) {
        throw new Error("Invalid JSON structure");
      }

      return Response.json({ 
        success: true, 
        templateJson: templateData 
      }, { status: 200 });

    } finally {
      // Clean up the temporary file
      try {
        await fs.unlink(outputFile);
      } catch (cleanupError) {
        console.error("Failed to clean up temporary file:", cleanupError);
      }
    }

  } catch (error) {
    console.error("Error in GET /api/playground:", error);
    return Response.json(
      { error: "Internal server error" }, 
      { status: 500 }
    );
  }
}