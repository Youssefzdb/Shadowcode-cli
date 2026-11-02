import React from 'react';
import { Box, Text } from 'ink';

export function Input(props: { value: string; prompt?: string }): React.ReactElement {
	return (
		<Box>
			<Text color="cyan" bold>
				{props.prompt ?? '> '}
			</Text>
			<Text>{props.value}</Text>
			<Text color="gray">▋</Text>
		</Box>
	);
}
