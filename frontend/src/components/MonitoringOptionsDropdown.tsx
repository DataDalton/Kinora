'use client';

import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  Eye,
  EyeOff,
  ChevronDown,
  Check,
  ArrowUpCircle,
  Calendar,
  CalendarCheck,
  CalendarX,
} from 'lucide-react';

type SeasonMonitoring = 'all' | 'none' | 'future' | 'existing';

interface MonitoringState {
  monitored: boolean;
  upgradeAllowed: boolean | null;
  seasonMonitoring?: SeasonMonitoring;
}

interface MonitoringOptionsDropdownProps {
  mediaType: 'movie' | 'show' | 'anime' | 'album' | 'artist' | 'track';
  mediaId: number;
  currentState: MonitoringState;
  showSeasonOptions?: boolean;
  onUpdate?: (newState: MonitoringState) => void;
}

interface MonitoringOption {
  id: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  action: () => void;
  active?: boolean;
}

export default function MonitoringOptionsDropdown({
  mediaType,
  mediaId,
  currentState,
  showSeasonOptions = false,
  onUpdate,
}: MonitoringOptionsDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [buttonRect, setButtonRect] = useState<DOMRect | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const updateMonitoringMutation = useMutation({
    mutationFn: async (payload: Partial<MonitoringState>) => {
      // Music types (artist, album, track) are under /music prefix
      const isMusicType = ['artist', 'album', 'track'].includes(mediaType);
      const endpoint = isMusicType
        ? `/music/${mediaType}s/${mediaId}/monitoring`
        : `/${mediaType}s/${mediaId}/monitoring`;
      const response = await api.put(endpoint, payload);
      return response.data;
    },
    onSuccess: (_, variables) => {
      const newState = { ...currentState, ...variables };
      queryClient.invalidateQueries({ queryKey: [mediaType, mediaId] });
      // When monitored status changes, also refetch seasons/episodes since they cascade
      if ('monitored' in variables) {
        if (mediaType === 'show') {
          queryClient.invalidateQueries({ queryKey: ['seasons', mediaId] });
          queryClient.invalidateQueries({ queryKey: ['episodes', mediaId] });
        } else if (mediaType === 'anime') {
          queryClient.invalidateQueries({ queryKey: ['anime-episodes', mediaId] });
        }
      }
      onUpdate?.(newState);
    },
  });

  const updateButtonRect = () => {
    if (buttonRef.current) {
      setButtonRect(buttonRef.current.getBoundingClientRect());
    }
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(target) &&
        buttonRef.current &&
        !buttonRef.current.contains(target)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (isOpen) {
      updateButtonRect();
      window.addEventListener('scroll', updateButtonRect, true);
      window.addEventListener('resize', updateButtonRect);
      return () => {
        window.removeEventListener('scroll', updateButtonRect, true);
        window.removeEventListener('resize', updateButtonRect);
      };
    }
  }, [isOpen]);

  const handleToggleMonitored = () => {
    updateMonitoringMutation.mutate({ monitored: !currentState.monitored });
  };

  const handleToggleUpgrade = () => {
    const newValue = currentState.upgradeAllowed === null
      ? true
      : currentState.upgradeAllowed
        ? false
        : null;
    updateMonitoringMutation.mutate({ upgradeAllowed: newValue });
  };

  const handleSeasonMonitoring = (mode: SeasonMonitoring) => {
    updateMonitoringMutation.mutate({ seasonMonitoring: mode });
  };

  const mainOptions: MonitoringOption[] = [
    {
      id: 'monitor',
      label: currentState.monitored ? 'Monitored' : 'Not Monitored',
      description: currentState.monitored
        ? 'Actively searching for downloads'
        : 'Not searching for downloads',
      icon: currentState.monitored
        ? <Eye className="w-4 h-4 text-primary" />
        : <EyeOff className="w-4 h-4 text-muted-foreground" />,
      action: handleToggleMonitored,
      active: currentState.monitored,
    },
  ];

  const upgradeOption: MonitoringOption = {
    id: 'upgrade',
    label: currentState.upgradeAllowed === null
      ? 'Upgrades: Profile Default'
      : currentState.upgradeAllowed
        ? 'Upgrades: Allowed'
        : 'Upgrades: Disabled',
    description: currentState.upgradeAllowed === null
      ? 'Using media profile setting'
      : currentState.upgradeAllowed
        ? 'Will upgrade to better quality'
        : 'Will not upgrade existing files',
    icon: <ArrowUpCircle className={`w-4 h-4 ${
      currentState.upgradeAllowed === true ? 'text-green-500' :
      currentState.upgradeAllowed === false ? 'text-destructive' :
      'text-muted-foreground'
    }`} />,
    action: handleToggleUpgrade,
    active: currentState.upgradeAllowed === true,
  };

  const seasonOptions: MonitoringOption[] = showSeasonOptions ? [
    {
      id: 'all',
      label: 'Monitor All Seasons',
      description: 'Monitor all existing and future seasons',
      icon: <CalendarCheck className="w-4 h-4" />,
      action: () => handleSeasonMonitoring('all'),
      active: currentState.seasonMonitoring === 'all',
    },
    {
      id: 'future',
      label: 'Monitor Future Only',
      description: 'Only monitor new seasons as they air',
      icon: <Calendar className="w-4 h-4" />,
      action: () => handleSeasonMonitoring('future'),
      active: currentState.seasonMonitoring === 'future',
    },
    {
      id: 'existing',
      label: 'Monitor Existing Only',
      description: 'Only monitor currently available seasons',
      icon: <CalendarCheck className="w-4 h-4" />,
      action: () => handleSeasonMonitoring('existing'),
      active: currentState.seasonMonitoring === 'existing',
    },
    {
      id: 'none',
      label: 'Monitor No Seasons',
      description: 'Do not monitor any seasons',
      icon: <CalendarX className="w-4 h-4" />,
      action: () => handleSeasonMonitoring('none'),
      active: currentState.seasonMonitoring === 'none',
    },
  ] : [];

  const getUpgradeLabel = () => {
    if (currentState.upgradeAllowed === null) return 'Default';
    if (currentState.upgradeAllowed) return 'On';
    return 'Off';
  };

  const handleButtonClick = () => {
    if (!isOpen) {
      updateButtonRect();
    }
    setIsOpen(!isOpen);
  };

  const getDropdownStyle = (): React.CSSProperties => {
    if (!buttonRect) return {};

    const spaceBelow = window.innerHeight - buttonRect.bottom - 16;

    return {
      top: buttonRect.bottom + 8,
      left: buttonRect.left,
      maxHeight: Math.max(Math.min(spaceBelow, 400), 150),
    };
  };

  const dropdownMenu = isOpen && typeof document !== 'undefined' && buttonRect ? createPortal(
    <div
      ref={dropdownRef}
      className="fixed z-50 w-72 bg-background rounded-lg border border-border shadow-xl overflow-y-auto"
      style={getDropdownStyle()}
    >
      <div className="p-2">
        <div className="text-xs font-medium text-muted-foreground px-2 py-1 mb-1">
          Monitoring
        </div>
        {mainOptions.map((option) => (
          <button
            key={option.id}
            onClick={() => {
              option.action();
            }}
            className="w-full flex items-start gap-3 px-2 py-2 hover:bg-muted rounded-lg transition text-left cursor-pointer"
          >
            <div className="mt-0.5">{option.icon}</div>
            <div className="flex-1">
              <p className="text-sm font-medium">{option.label}</p>
              <p className="text-xs text-muted-foreground">{option.description}</p>
            </div>
            {option.active && (
              <Check className="w-4 h-4 text-primary mt-0.5" />
            )}
          </button>
        ))}
      </div>

      <div className="border-t border-border p-2">
        <div className="text-xs font-medium text-muted-foreground px-2 py-1 mb-1">
          Quality Upgrades
        </div>
        <button
          onClick={upgradeOption.action}
          className="w-full flex items-start gap-3 px-2 py-2 hover:bg-muted rounded-lg transition text-left cursor-pointer"
        >
          <div className="mt-0.5">{upgradeOption.icon}</div>
          <div className="flex-1">
            <p className="text-sm font-medium">{upgradeOption.label}</p>
            <p className="text-xs text-muted-foreground">{upgradeOption.description}</p>
          </div>
          <div className="flex items-center gap-1 mt-0.5">
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              currentState.upgradeAllowed === true ? 'bg-green-500/20 text-green-500' :
              currentState.upgradeAllowed === false ? 'bg-destructive/20 text-destructive' :
              'bg-muted text-muted-foreground'
            }`}>
              {getUpgradeLabel()}
            </span>
          </div>
        </button>
      </div>

      {showSeasonOptions && seasonOptions.length > 0 && (
        <div className="border-t border-border p-2">
          <div className="text-xs font-medium text-muted-foreground px-2 py-1 mb-1">
            Season Monitoring
          </div>
          {seasonOptions.map((option) => (
            <button
              key={option.id}
              onClick={() => {
                option.action();
                setIsOpen(false);
              }}
              className="w-full flex items-start gap-3 px-2 py-2 hover:bg-muted rounded-lg transition text-left cursor-pointer"
            >
              <div className="mt-0.5">{option.icon}</div>
              <div className="flex-1">
                <p className="text-sm font-medium">{option.label}</p>
                <p className="text-xs text-muted-foreground">{option.description}</p>
              </div>
              {option.active && (
                <Check className="w-4 h-4 text-primary mt-0.5" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>,
    document.body
  ) : null;

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        onClick={handleButtonClick}
        disabled={updateMonitoringMutation.isPending}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg transition text-sm font-medium cursor-pointer ${
          currentState.monitored
            ? 'bg-primary/20 text-primary hover:bg-primary/30'
            : 'bg-muted text-muted-foreground hover:bg-muted/80'
        }`}
      >
        {updateMonitoringMutation.isPending ? (
          <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
        ) : currentState.monitored ? (
          <Eye className="w-4 h-4" />
        ) : (
          <EyeOff className="w-4 h-4" />
        )}
        <span>{currentState.monitored ? 'Monitored' : 'Unmonitored'}</span>
        <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {dropdownMenu}
    </div>
  );
}
