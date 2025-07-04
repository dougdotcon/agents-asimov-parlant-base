/* eslint-disable react-hooks/exhaustive-deps */
import {memo, ReactElement, useEffect, useRef, useState} from 'react';
import {EventInterface} from '@/utils/interfaces';
import Spacer from '../ui/custom/spacer';
import {twJoin, twMerge} from 'tailwind-merge';
import Markdown from '../markdown/markdown';
import Tooltip from '../ui/custom/tooltip';
import {Textarea} from '../ui/textarea';
import {Button} from '../ui/button';
import {useAtom} from 'jotai';
import {agentAtom, customerAtom, sessionAtom} from '@/store';
import {getAvatarColor} from '../avatar/avatar';
import MessageRelativeTime from './message-relative-time';
import EnhancedMessage from './enhanced-message';

interface Props {
	event: EventInterface;
	isContinual: boolean;
	isRegenerateHidden?: boolean;
	isFirstMessageInDate?: boolean;
	showLogsForMessage?: EventInterface | null;
	regenerateMessageFn?: (sessionId: string) => void;
	resendMessageFn?: (sessionId: string, text?: string) => void;
	showLogs: (event: EventInterface) => void;
	setIsEditing?: React.Dispatch<React.SetStateAction<boolean>>;
}

const MessageBubble = ({event, isFirstMessageInDate, showLogs, isContinual, showLogsForMessage, setIsEditing}: Props) => {
	const ref = useRef<HTMLDivElement>(null);
	const [agent] = useAtom(agentAtom);
	const [customer] = useAtom(customerAtom);
	const markdownRef = useRef<HTMLSpanElement>(null);
	const [rowCount, setRowCount] = useState(1);

	useEffect(() => {
		if (!markdownRef?.current) return;
		const rowCount = Math.floor(markdownRef.current.offsetHeight / 24);
		setRowCount(rowCount + 1);
	}, [markdownRef]);

	const isOneLiner = rowCount === 1;

	const isCustomer = event.source === 'customer' || event.source === 'customer_ui';
	const serverStatus = event.serverStatus;
	const isGuest = customer?.name === '<guest>';
	const customerName = isGuest ? 'G' : customer?.name?.[0]?.toUpperCase();
	const isViewingCurrentMessage = showLogsForMessage && showLogsForMessage.id === event.id;
	const colorPallete = getAvatarColor((isCustomer ? customer?.id : agent?.id) || '', isCustomer ? 'customer' : 'agent');
	const name = isCustomer ? customer?.name : agent?.name;
	const formattedName = name === '<guest>' ? 'Guest' : name;

	return (
		<>
			<div className={(isCustomer ? 'justify-end' : 'justify-start') + ' flex-1 flex max-w-[min(1000px,100%)] items-end w-[calc(100%-412px)]  max-[1440px]:w-[calc(100%-160px)] max-[900px]:w-[calc(100%-40px)]'}>
				<div className='relative max-w-[80%]'>
					{(!isContinual || isFirstMessageInDate) && (
						<div className={twJoin('flex justify-between items-center mb-[12px] mt-[46px]', isFirstMessageInDate && 'mt-[0]', isCustomer && 'flex-row-reverse')}>
							<div className={twJoin('flex gap-[8px] items-center', isCustomer && 'flex-row-reverse')}>
								<div
									className='size-[26px] flex rounded-[6.5px] select-none items-center justify-center font-semibold'
									style={{color: isCustomer ? 'white' : colorPallete.text, background: isCustomer ? colorPallete.iconBackground : colorPallete?.background}}>
									{(isCustomer ? customerName?.[0] : agent?.name?.[0])?.toUpperCase()}
								</div>
								<div className='font-medium text-[14px] text-[#282828]'>{formattedName}</div>
							</div>
							<MessageRelativeTime event={event} />
						</div>
					)}
					<div className='flex items-center relative max-w-full'>
						{isCustomer && (
							<div className={twMerge('self-stretch absolute -left-[40px] top-[50%] -translate-y-1/2 items-center flex invisible group-hover/main:visible peer-hover:visible hover:visible')}>
								<Tooltip value='Edit' side='left'>
									<div data-testid='edit-button' role='button' onClick={() => setIsEditing?.(true)} className='group cursor-pointer'>
										<img src='icons/edit-message.svg' alt='edit' className='block rounded-[10px] group-hover:bg-[#EBECF0] size-[30px] p-[5px]' />
									</div>
								</Tooltip>
							</div>
						)}
						<div className='max-w-full'>
							<div
								ref={ref}
								tabIndex={0}
								data-testid='message'
								onClick={() => showLogs(event)}
								className={twMerge(
									'bg-blue-light border-[2px] hover:bg-[#F5F9FF] text-black border-transparent cursor-pointer',
									isViewingCurrentMessage && '!bg-white hover:!bg-white border-[#EEEEEE] shadow-main',
									isCustomer && serverStatus === 'error' && '!bg-[#FDF2F1] hover:!bg-[#F5EFEF]',
									'max-w-[min(560px,100%)] peer w-[560px] flex items-center relative',
									event?.serverStatus === 'pending' && 'opacity-50',
									isOneLiner ? 'p-[13px_22px_17px_22px] rounded-[16px]' : 'p-[20px_22px_24px_22px] rounded-[22px]'
								)}>
								<div className={twMerge('markdown overflow-hidden relative min-w-[200px] max-w-[608px] [word-break:break-word] font-light text-[16px] pe-[38px]')}>
									<span ref={markdownRef}>
										<Markdown className={twJoin(!isOneLiner && 'leading-[26px]')}>{event?.data?.message}</Markdown>
									</span>
								</div>
								<div className={twMerge('flex h-full font-normal text-[11px] text-[#AEB4BB] pe-[20px] font-inter self-end items-end whitespace-nowrap leading-[14px]', isOneLiner ? 'ps-[12px]' : '')}></div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</>
	);
};

const MessageEditing = ({event, resendMessageFn, setIsEditing}: Props) => {
	const ref = useRef<HTMLDivElement>(null);
	const textArea = useRef<HTMLTextAreaElement>(null);
	const [textValue, setTextValue] = useState(event?.data?.message || '');
	const [session] = useAtom(sessionAtom);

	useEffect(() => {
		textArea?.current?.select();
	}, [textArea?.current]);

	useEffect(() => {
		ref?.current?.scrollIntoView({behavior: 'smooth', block: 'nearest'});
	}, [ref?.current]);

	return (
		<div ref={ref} className='w-full p-[16px] ps-[6px] pe-[6px] rounded-[16px] max-w-[min(560px,90%)] rounded-br-none border origin-bottom bg-[#f5f6f8] ' style={{transformOrigin: 'bottom'}}>
			<Textarea ref={textArea} className='[direction:ltr] resize-none h-[120px] pe-[108px] !ring-0 !ring-offset-0 border-none ps-[22px] bg-[#f5f6f8]' onChange={(e) => setTextValue(e.target.value)} defaultValue={textValue} />
			<div className='pt-[10px] flex justify-end gap-[10px] pe-[12px] [direction:ltr]'>
				<Button variant='ghost' onClick={() => setIsEditing?.(false)} className='rounded-[10px] hover:bg-white'>
					Cancel
				</Button>
				<Button
					disabled={!textValue?.trim() || textValue?.trim() === event?.data?.message}
					className='rounded-[10px]'
					onClick={() => {
						resendMessageFn?.(session?.id || '', textValue?.trim());
						setIsEditing?.(false);
					}}>
					Apply
				</Button>
			</div>
		</div>
	);
};

function Message({event, isFirstMessageInDate, isContinual, showLogs, showLogsForMessage, resendMessageFn, regenerateMessageFn}: Props): ReactElement {
	const [session] = useAtom(sessionAtom);

	// Convert EventInterface to format expected by EnhancedMessage
	const messageProps = {
		id: event.id,
		content: event.data?.message || '',
		role: (event.source === 'customer' || event.source === 'customer_ui') ? 'user' as const : 'assistant' as const,
		timestamp: new Date(event.creation_utc),
		onEdit: (id: string, newContent: string) => {
			resendMessageFn?.(session?.id || '', newContent);
		},
		onRegenerate: regenerateMessageFn ? (id: string) => {
			regenerateMessageFn(session?.id || '');
		} : undefined,
		onCopy: (content: string) => {
			console.log('Copied:', content);
		},
		onFeedback: (id: string, type: 'positive' | 'negative') => {
			console.log('Feedback:', id, type);
		},
		className: "max-w-[1000px] mx-auto"
	};

	return (
		<div className="w-full">
			<EnhancedMessage {...messageProps} />
		</div>
	);
}

export default memo(Message, (prevProps, nextProps) => {
	const prevIsShown = prevProps.showLogsForMessage?.id === prevProps.event.id;
	const nextIsShown = nextProps.showLogsForMessage?.id === nextProps.event.id;
	return prevIsShown === nextIsShown && prevProps.event.id === nextProps.event.id;
});
