// Copyright byteyang. All Rights Reserved.
#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#include "Utils/NexusMcpImageUtils.h"
#include "Misc/Base64.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/Guid.h"
#include "HAL/FileManager.h"
#include "Dom/JsonValue.h"
#if WITH_EDITOR
#include "Utils/NexusCaptureUtils.h"
#include "Misc/ScopeExit.h"
#endif

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusMcpImageContentTest, "NexusLink.Protocol.ImageContent", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusMcpImageContentTest::RunTest(const FString&)
{
	const FString Prefix = FPaths::ProjectSavedDir() / (TEXT("NexusImageTest_") + FGuid::NewGuid().ToString(EGuidFormats::Digits));
	TArray<uint8> Png; FBase64::Decode(TEXT("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jWZkAAAAASUVORK5CYII="), Png);
	TArray<FString> Paths;
	for (int32 I = 0; I < 5; ++I) { const FString Path = Prefix + FString::FromInt(I) + TEXT(".png"); TestTrue(TEXT("Write generated fixture"), FFileHelper::SaveArrayToFile(Png, *Path)); Paths.Add(Path); }
	auto Metadata = MakeShared<FJsonObject>(); Metadata->SetStringField(TEXT("FilePath"), Paths[0]);
	auto Structured = MakeShared<FJsonObject>(); Structured->SetObjectField(TEXT("structuredContent"), Metadata);
	FNexusMcpImageUtils::AppendContent({}, Structured);
	TestFalse(TEXT("Business FilePath is never promoted implicitly"), Structured->HasField(TEXT("content")));
	FNexusMcpImageUtils::AppendContent(Paths, Structured);
	const auto& Content = Structured->GetArrayField(TEXT("content"));
	int32 Images = 0;
	for (const auto& Item : Content) if (Item->AsObject()->GetStringField(TEXT("type")) == TEXT("image"))
	{
		++Images; TArray<uint8> Roundtrip; FBase64::Decode(Item->AsObject()->GetStringField(TEXT("data")), Roundtrip);
		TestTrue(TEXT("Image bytes roundtrip"), Roundtrip == Png);
		TestEqual(TEXT("Standard MIME type"), Item->AsObject()->GetStringField(TEXT("mimeType")), FString(TEXT("image/png")));
	}
	TestEqual(TEXT("Image count is bounded"), Images, 4);
	TestEqual(TEXT("Omission is explicit"), Content.Num(), 5);
	TestEqual(TEXT("FilePath metadata retained"), Structured->GetObjectField(TEXT("structuredContent"))->GetStringField(TEXT("FilePath")), Paths[0]);
	auto Text = MakeShared<FJsonObject>(); auto Block = MakeShared<FJsonObject>(); Block->SetStringField(TEXT("type"), TEXT("text")); Block->SetStringField(TEXT("text"), TEXT("original metadata")); Text->SetArrayField(TEXT("content"), {MakeShared<FJsonValueObject>(Block)});
	FNexusMcpImageUtils::AppendContent({Paths[0], Paths[0]}, Text);
	TestEqual(TEXT("Text plus one deduplicated image"), Text->GetArrayField(TEXT("content")).Num(), 2);
	TestEqual(TEXT("Legacy text retained"), Text->GetArrayField(TEXT("content"))[0]->AsObject()->GetStringField(TEXT("text")), FString(TEXT("original metadata")));
	TArray<uint8> Large; Large.SetNumZeroed(4 * 1024 * 1024 + 1); const FString BigPath = Prefix + TEXT("large.png"); FFileHelper::SaveArrayToFile(Large, *BigPath);
	auto Rejected = MakeShared<FJsonObject>(); FNexusMcpImageUtils::AppendContent({BigPath}, Rejected);
	TestEqual(TEXT("Oversize attachment yields a note"), Rejected->GetArrayField(TEXT("content"))[0]->AsObject()->GetStringField(TEXT("type")), FString(TEXT("text")));
	for (const auto& Path : Paths) IFileManager::Get().Delete(*Path);
	IFileManager::Get().Delete(*BigPath);
	return true;
}

#if WITH_EDITOR
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusCaptureRetentionTest, "NexusLink.Protocol.CaptureRetention", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusCaptureRetentionTest::RunTest(const FString&)
{
	IFileManager& Manager = IFileManager::Get();
	const FString Directory = FPaths::ProjectSavedDir() / (TEXT("NexusCaptureRetention_") + FGuid::NewGuid().ToString(EGuidFormats::Digits));
	if (!TestTrue(TEXT("Create isolated capture directory"), Manager.MakeDirectory(*Directory, true))) return false;
	TArray<FString> Paths;
	ON_SCOPE_EXIT { for (const FString& Path : Paths) Manager.Delete(*Path); Manager.DeleteDirectory(*Directory); };
	for (int32 CaptureIndex = 0; CaptureIndex < 20; ++CaptureIndex)
	{
		const FString Path = Directory / FString::Printf(TEXT("NexusCapture_slate_%02d.png"), CaptureIndex);
		Paths.Add(Path);
		TestTrue(TEXT("Write old Slate capture"), FFileHelper::SaveStringToFile(TEXT("capture"), *Path));
		Manager.SetTimeStamp(*Path, FDateTime(2020, 1, 1) + FTimespan::FromSeconds(CaptureIndex));
	}
	for (const TCHAR* Name : {TEXT("NexusCapture_Editor_new.png"), TEXT("NexusCapture_Editor_new.jpg")})
	{
		const FString Path = Directory / Name;
		Paths.Add(Path);
		TestTrue(TEXT("Write recent Editor capture"), FFileHelper::SaveStringToFile(TEXT("capture"), *Path));
		Manager.SetTimeStamp(*Path, FDateTime(2022, 1, 1));
	}
	const FString OtherFile = Directory / TEXT("User.png"); Paths.Add(OtherFile);
	TestTrue(TEXT("Write unrelated file"), FFileHelper::SaveStringToFile(TEXT("user"), *OtherFile));
	FNexusCaptureUtils::CleanupOldCaptures(Directory);
	TestTrue(TEXT("New PNG survives mixed capture types"), Manager.FileExists(*Paths[20]));
	TestTrue(TEXT("New JPEG survives mixed capture types"), Manager.FileExists(*Paths[21]));
	TestFalse(TEXT("Oldest capture removed"), Manager.FileExists(*Paths[0]));
	TestFalse(TEXT("Second oldest capture removed"), Manager.FileExists(*Paths[1]));
	TestTrue(TEXT("Unrelated file retained"), Manager.FileExists(*OtherFile));
	return true;
}
#endif
