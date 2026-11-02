import React from 'react';
import { Box, Text, useInput } from 'ink';

export function PermissionPrompt(props: {
	prompt: string;
	onAnswer: (allowed: boolean) => void;
}): React.ReactElement {
	useInput((_input, key) => {
		if (key.return) return;
	});
	return (
		<Box borderStyle="double" borderColor="red" paddingX={1} flexDirection="column">
			<Text bold color="red">
				Permission required
			</Text>
			<Text>{props.prompt}</Text>
			<Text color="gray">Press y to allow, n to deny. In subprocess mode destructive tools are denied unless --allow-destructive was passed.</Text>
		</Box>
	);
}
