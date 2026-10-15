import { createContext } from 'react';

// The real module needs createNavigatorFactory, which the native mock lacks. Outside a
// tab navigator this context is undefined — what screens rendered alone in tests are.
// BaseLayout reads it to decide on the bottom safe-area edge.
export const BottomTabBarHeightContext = createContext(undefined);
