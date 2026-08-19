import React, { useState } from 'react';
import { View, Text, ActivityIndicator } from 'react-native';
import { Image, Button } from '@rneui/themed';
import { api } from '../../lib';
import styles from './styles';

const ImageView = ({
  label,
  uri,
  textTestID,
  imageTestID,
  onRetake = null,
  onPickGallery = null,
  missingText = '',
  retakeLabel = '',
  galleryLabel = '',
  loadFailedText = '',
  tryAgainLabel = '',
  isRetaking = false,
  processingLabel = '',
}) => {
  // No upfront file check: the Image load itself reports a dead file:// path
  // via onError, so missing files cost no extra I/O.
  //
  // Remember *which* uri failed rather than a boolean. Picking a replacement
  // photo changes `uri`, so the comparison below goes false on its own — the
  // preview appears without this component having to be remounted and without
  // an effect to reset the flag.
  const [failedUri, setFailedUri] = useState(null);
  // Bumping this remounts the Image, which is what makes "Try again" re-request it
  const [reloadKey, setReloadKey] = useState(0);
  // get base path from http://example.com/api/v2/any/ to http://example.com
  const baseURL = api.getConfig().baseURL?.replace(/\/api\/v\d+\/.*$/, '');
  const imageURL =
    !uri?.includes('file://') && !uri?.startsWith('http') && !uri.startsWith('data:image')
      ? `${baseURL}${uri}`
      : uri;
  // Repair only makes sense for local files pending upload, not remote images
  const isLocalFile = !!uri?.startsWith('file://');
  const showRetake = !!onRetake && isLocalFile;
  const showGallery = !!onPickGallery && isLocalFile;
  const loadFailed = !!uri && failedUri === uri;

  const handleRetry = () => {
    setFailedUri(null);
    setReloadKey((k) => k + 1);
  };

  let content = (
    // Keyed on the uri too, so a replacement photo is fetched fresh rather than
    // served from the cached decode of the previous one
    <Image
      key={`${uri}-${reloadKey}`}
      source={{ uri: imageURL }}
      testID={imageTestID}
      style={styles.image}
      onError={() => setFailedUri(uri)}
    />
  );
  if (loadFailed) {
    content = isLocalFile ? (
      <View>
        <Text style={styles.missingText} testID={`${imageTestID}-missing`}>
          {missingText}
        </Text>
        <View style={styles.buttonRow}>
          {showRetake && (
            <Button
              title={retakeLabel}
              onPress={onRetake}
              testID={`${imageTestID}-retake`}
              containerStyle={styles.repairButton}
            />
          )}
          {showGallery && (
            <Button
              title={galleryLabel}
              onPress={onPickGallery}
              testID={`${imageTestID}-gallery`}
              containerStyle={styles.repairButton}
            />
          )}
        </View>
      </View>
    ) : (
      // Remote path — the file lives on the server, so this is a connectivity
      // problem. Never offer retake/gallery here: there is nothing local to repair.
      <View>
        <Text style={styles.missingText} testID={`${imageTestID}-load-failed`}>
          {loadFailedText}
        </Text>
        <Button title={tryAgainLabel} onPress={handleRetry} testID={`${imageTestID}-reload`} />
      </View>
    );
  }
  if (isRetaking) {
    content = (
      <View style={styles.processingContainer} testID={`${imageTestID}-processing`}>
        <ActivityIndicator size="small" color="dodgerblue" />
        <Text style={styles.processingText}>{processingLabel}</Text>
      </View>
    );
  }

  return (
    <View style={styles.containerImage}>
      <Text style={styles.title} testID={textTestID}>
        {label}
      </Text>
      {content}
    </View>
  );
};

export default ImageView;
