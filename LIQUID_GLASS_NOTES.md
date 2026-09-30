# Cassette Liquid Glass v8

## Glass / window fix

The large rectangular compositor surface seen on high-DPI Windows displays was caused by passing Qt logical dimensions directly to `CreateRoundRectRgn`. Windows native window regions use physical pixels. At 125% scaling, for example, a 510px Qt widget becomes roughly 638 physical pixels wide, leaving an unclipped rectangular acrylic tail.

The v8 implementation fixes this by:

- converting the Qt logical size to physical pixels with `devicePixelRatioF()` before creating the native rounded region;
- scaling the native corner radius by the same DPR;
- applying the compositor after the native HWND is shown;
- retaining the live Windows acrylic compositor;
- keeping `WA_TranslucentBackground`;
- never taking desktop screenshots;
- keeping all existing Spotify, lyrics, reel, gesture, tray, animation and control logic.

This specifically addresses the rectangular/white-glass artifact visible at non-100% Windows display scaling.
