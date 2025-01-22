import { useState } from 'react';
import { Button } from "/components/ui/button";
import { Input } from "/components/ui/input";
import { Label } from "/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "/components/ui/card";
import { Play, Stop } from "lucide-react";

export default function UserInputForm() {
  const [initialPrompt, setInitialPrompt] = useState('');
  const [templateName, setTemplateName] = useState('');
  const [model, setModel] = useState('');
  const [maxIterations, setMaxIterations] = useState('');
  const [timeout, setTimeout] = useState('');
  const [isLoopRunning, setIsLoopRunning] = useState(false);

  const handleStartLoop = () => {
    // Logic to start the development loop
    setIsLoopRunning(true);
    console.log('Loop started with:', { initialPrompt, templateName, model, maxIterations, timeout });
  };

  const handleStopLoop = () => {
    // Logic to stop the development loop
    setIsLoopRunning(false);
    console.log('Loop stopped');
  };

  const isFormValid = () => {
    return initialPrompt && templateName && model && maxIterations && timeout;
  };

  return (
    <Card className="w-full max-w-3xl mx-auto">
      <CardHeader>
        <CardTitle>Development Loop Configuration</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="space-y-4">
          <div>
            <Label htmlFor="initial-prompt">Initial Prompt</Label>
            <Input
              id="initial-prompt"
              value={initialPrompt}
              onChange={(e) => setInitialPrompt(e.target.value)}
              placeholder="Enter initial prompt"
              className="mt-2"
            />
          </div>
          <div>
            <Label htmlFor="template-name">Template Name</Label>
            <Input
              id="template-name"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              placeholder="Enter template name"
              className="mt-2"
            />
          </div>
          <div>
            <Label htmlFor="model">Model</Label>
            <Input
              id="model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="Enter model"
              className="mt-2"
            />
          </div>
          <div>
            <Label htmlFor="max-iterations">Max Iterations</Label>
            <Input
              id="max-iterations"
              value={maxIterations}
              onChange={(e) => setMaxIterations(e.target.value)}
              placeholder="Enter max iterations"
              className="mt-2"
            />
          </div>
          <div>
            <Label htmlFor="timeout">Timeout</Label>
            <Input
              id="timeout"
              value={timeout}
              onChange={(e) => setTimeout(e.target.value)}
              placeholder="Enter timeout"
              className="mt-2"
            />
          </div>
          <div className="flex justify-between">
            <Button
              variant="secondary"
              onClick={handleStartLoop}
              disabled={!isFormValid() || isLoopRunning}
            >
              <Play className="mr-2 h-4 w-4" /> Start Loop
            </Button>
            <Button
              variant="destructive"
              onClick={handleStopLoop}
              disabled={!isLoopRunning}
            >
              <Stop className="mr-2 h-4 w-4" /> Stop Loop
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
