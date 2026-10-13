"use client";

import { useEffect, useRef, type MouseEvent } from "react";

// Popups currently open, oldest first. Escape only closes the last one, so a dialog
// opened on top of another closes on its own.
const openPopups: symbol[] = [];

interface ModalDismissOptions {
	onClose: () => void;
	// For popups that stay mounted while hidden. Leave unset for popups rendered only
	// while open.
	isOpen?: boolean;
	// Confirmations and read-only popups close on a click outside. Forms leave this off
	// so a stray click does not throw away what was typed.
	closeOnOutsideClick?: boolean;
	// Holds the popup open while it is working, such as during a delete or a save.
	disabled?: boolean;
}

export interface BackdropProps {
	onMouseDown: (event: MouseEvent<HTMLElement>) => void;
	onClick: (event: MouseEvent<HTMLElement>) => void;
}

/**
 * Closes a popup on Escape, and on a click outside it when closeOnOutsideClick is set.
 * Spread the returned props on the full-screen backdrop element. A click only counts
 * as outside when it both starts and ends on the backdrop itself, so dragging a text
 * selection out of the dialog does not close it.
 */
export function useModalDismiss({
	onClose,
	isOpen = true,
	closeOnOutsideClick = false,
	disabled = false,
}: ModalDismissOptions): BackdropProps {
	const onCloseRef = useRef(onClose);
	const disabledRef = useRef(disabled);
	const pressStartedOnBackdrop = useRef(false);

	// Handlers read the latest values without re-registering the Escape listener.
	useEffect(() => {
		onCloseRef.current = onClose;
		disabledRef.current = disabled;
	});

	useEffect(() => {
		if (!isOpen) return;
		const id = Symbol("popup");
		openPopups.push(id);

		const handleKeyDown = (event: KeyboardEvent) => {
			if (event.key !== "Escape") return;
			if (openPopups[openPopups.length - 1] !== id) return;
			if (disabledRef.current) return;
			event.preventDefault();
			onCloseRef.current();
		};
		document.addEventListener("keydown", handleKeyDown);

		return () => {
			document.removeEventListener("keydown", handleKeyDown);
			const index = openPopups.indexOf(id);
			if (index !== -1) openPopups.splice(index, 1);
		};
	}, [isOpen]);

	return {
		onMouseDown: (event) => {
			pressStartedOnBackdrop.current =
				event.target === event.currentTarget;
		},
		onClick: (event) => {
			const startedOnBackdrop = pressStartedOnBackdrop.current;
			pressStartedOnBackdrop.current = false;
			if (!closeOnOutsideClick || disabledRef.current) return;
			if (startedOnBackdrop && event.target === event.currentTarget) {
				onCloseRef.current();
			}
		},
	};
}
